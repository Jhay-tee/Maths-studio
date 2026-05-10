from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import asyncio
from google import genai
from google.genai import types
import base64
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from solvers.algebra import solve_algebra
from solvers.structural import solve_structural
from solvers.mechanics import solve_mechanics
from solvers.calculus import solve_calculus
from solvers.fluids import solve_fluids
from solvers.thermodynamics import solve_thermo

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]

# ─────────────────────────────────────────────
# GEMINI IS A ROUTER ONLY — NOT A SOLVER
# ─────────────────────────────────────────────
ROUTING_SYSTEM_PROMPT = """
You are ONLY a classification and routing layer for an engineering backend system.

You must NOT:
- Solve problems
- Perform any calculations
- Choose solving methods
- Generate final answers
- Act as a physics, math, or engineering engine
- Behave like a chatbot or assistant

YOUR ONLY JOB:
Given a user input (text or image), identify and extract ALL engineering sub-problems present.
For each sub-problem, produce a routing label and clean structured data for the backend solver.

DOMAIN OPTIONS:
- algebra
- calculus
- mechanics
- structural
- fluids
- thermo
- unknown

OUTPUT FORMAT — return ONLY this JSON, no explanation, no markdown, no extra text:
{
  "summary": "brief overall description of all problems",
  "sub_problems": [
    {
      "id": "p1",
      "domain": "structural",
      "problem_type": "simply_supported_beam_udl",
      "input_summary": "clean restatement of this sub-problem with all given values",
      "parameters": {
        "key": "value with unit"
      },
      "options": [],
      "confidence": 0.95
    }
  ]
}

PARAMETER EXTRACTION RULES:
- Extract ALL numerical values with their units
- Normalize parameter names (e.g. "length", "load", "velocity", "temperature")
- If multiple sub-problems exist, split them into separate entries
- If options (A, B, C, D) are present, extract them into the "options" array as [{"label": "A", "val": ...}]
- If a value is ambiguous, include it with a note in the parameter name

IMPORTANT:
- You are a router. The backend handles ALL computation.
- Never include solution steps, answers, or calculations in your output.
- confidence is your certainty (0.0–1.0) that you correctly identified the domain and problem type.
"""


def convert_history(history: list) -> list:
    """
    Convert frontend history format:
      [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    into google-genai SDK types.Content objects.
    Skips empty entries. Maps "assistant" -> "model".
    """
    contents = []
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "").strip()
        if not content:
            continue
        sdk_role = "model" if role == "assistant" else "user"
        contents.append(
            types.Content(
                role=sdk_role,
                parts=[types.Part.from_text(text=content)],
            )
        )
    return contents


async def route_input(input_data: str, is_image: bool, history: list = None) -> dict:
    """
    Calls Gemini ONLY to classify and extract parameters.
    Gemini does zero computation here.
    """
    last_error = None
    for model_name in MODELS:
        try:
            contents = convert_history(history or [])

            if is_image:
                if "," in input_data:
                    input_data = input_data.split(",")[1]
                image_bytes = base64.b64decode(input_data)
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(
                                data=image_bytes, mime_type="image/jpeg"
                            ),
                            types.Part.from_text(
                                text="Extract and classify all engineering problems in this image. Return only the routing JSON."
                            ),
                        ],
                    )
                )
            else:
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(
                                text=f"Classify and extract parameters from this input. Return only the routing JSON.\n\nInput: {input_data}"
                            )
                        ],
                    )
                )

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=ROUTING_SYSTEM_PROMPT,
                    temperature=0.1,  # Low temp = deterministic routing
                ),
            )

            text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(text)
            data["_model"] = model_name
            logger.info(f"Routing result from {model_name}: {json.dumps(data, indent=2)}")
            return data

        except json.JSONDecodeError as e:
            logger.error(f"Model {model_name} returned invalid JSON: {e}")
            last_error = f"Router returned invalid JSON: {str(e)}"
            break
        except Exception as e:
            logger.warning(f"Model {model_name} failed in router: {e}")
            last_error = str(e)
            if "429" in last_error or "quota" in last_error.lower():
                continue
            break

    return {"error": last_error or "Routing failed"}


def make_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def make_error_event(message: str, problem_id: str = None) -> str:
    payload = {"type": "error", "message": message}
    if problem_id is not None:
        payload["problem_id"] = problem_id
    return f"data: {json.dumps(payload)}\n\n"


def select_solver(domain: str, problem_type: str):
    """
    Pure routing table. Maps domain + problem_type to the correct solver.
    No Gemini involved. No guessing.
    """
    d = domain.lower()
    pt = problem_type.lower()

    if d in ("algebra",) or any(k in pt for k in ["equation", "algebra", "polynomial", "linear", "quadratic"]):
        return solve_algebra

    if d in ("calculus",) or any(k in pt for k in ["integral", "derivative", "limit", "calculus", "differential"]):
        return solve_calculus

    if d in ("mechanics",) or any(k in pt for k in ["kinematics", "dynamics", "motion", "momentum", "projectile", "force", "newton"]):
        return solve_mechanics

    if d in ("structural",) or any(k in pt for k in ["beam", "truss", "structural", "bending", "shear", "reaction", "moment", "deflection", "udl", "point_load"]):
        return solve_structural

    if d in ("fluids",) or any(k in pt for k in ["fluid", "flow", "pressure", "bernoulli", "hydro", "pipe", "viscosity", "continuity"]):
        return solve_fluids

    if d in ("thermo",) or any(k in pt for k in ["heat", "temperature", "entropy", "enthalpy", "thermodynamic", "carnot", "cycle", "conduction", "convection"]):
        return solve_thermo

    return None


@app.post("/solve")
async def solve(request: Request):
    try:
        raw_data = await request.json()
    except Exception:
        async def _bad():
            yield make_error_event("Invalid JSON in request body")
        return StreamingResponse(_bad(), media_type="text/event-stream")

    user_input = raw_data.get("input", "").strip()
    input_type = raw_data.get("type", "text")
    history = raw_data.get("history", [])
    is_image = input_type == "image"

    if not user_input and not is_image:
        async def _missing():
            yield make_error_event("No input provided")
        return StreamingResponse(_missing(), media_type="text/event-stream")

    async def event_generator():
        # ── Step 1: Route via Gemini (classify only) ──
        yield make_event({
            "type": "step",
            "content": "Studio Kernel: Classifying and extracting parameters...",
        })

        routing = await route_input(user_input, is_image, history)

        if "error" in routing:
            yield make_error_event("Routing Failed: " + routing["error"])
            return

        sub_problems = routing.get("sub_problems", [])

        # Fallback: single-object response
        if not sub_problems and "domain" in routing:
            sub_problems = [routing]

        if not sub_problems:
            yield make_error_event("Could not extract any problems from the input. Please rephrase.")
            return

        yield make_event({
            "type": "meta",
            "summary": routing.get("summary", "Processing problems..."),
            "model": routing.get("_model", "unknown"),
            "count": len(sub_problems),
        })

        # ── Step 2: Dispatch each sub-problem to the correct solver ──
        for idx, sub in enumerate(sub_problems):
            domain = sub.get("domain", "unknown").lower()
            problem_type = sub.get("problem_type", "unknown").lower()
            problem_id = sub.get("id", f"p{idx}")
            confidence = sub.get("confidence", 0.0)

            yield make_event({
                "type": "step",
                "content": f"Dispatching Sub-problem {idx + 1}: [{domain}] {problem_type} (confidence: {confidence:.0%})",
            })

            # Pass parameters extracted by Gemini into the sub dict
            # so solvers can access sub["parameters"] directly
            if "parameters" not in sub:
                sub["parameters"] = {}

            # Also keep input_summary accessible as raw_query for solver compatibility
            sub["raw_query"] = sub.get("input_summary", user_input)
            sub["topic"] = domain  # backward-compat with solvers that read sub["topic"]

            solver_fn = select_solver(domain, problem_type)

            if not solver_fn:
                yield make_event({
                    "type": "final",
                    "answer": f"No solver available for domain '{domain}' / type '{problem_type}'.",
                    "problem_id": problem_id,
                })
                continue

            try:
                async for chunk in solver_fn(sub):
                    chunk["problem_id"] = problem_id

                    # Option matching on final chunk
                    if chunk.get("type") == "final" and sub.get("options"):
                        ans_text = str(chunk.get("answer", ""))
                        matched = False
                        for opt in sub["options"]:
                            opt_label = str(opt.get("label", "")).lower()
                            opt_val = str(opt.get("val", ""))
                            if opt_label in ans_text.lower() or opt_val in ans_text:
                                chunk["answer"] = ans_text + f"\n\n**Correct Option: {opt['label']}**"
                                matched = True
                                break
                        if not matched:
                            chunk["answer"] = ans_text + "\n\n**Note: No option matched the computed result.**"

                    yield make_event(chunk)

            except Exception as e:
                logger.error(f"Solver error in sub-problem {idx} ({domain}/{problem_type}): {e}")
                yield make_error_event(
                    f"Solver Error [{domain}]: {str(e)}", problem_id
                )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9999)
