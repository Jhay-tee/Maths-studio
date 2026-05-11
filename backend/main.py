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
import importlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok", "uptime": "running"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

MODELS = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash"]

# ─────────────────────────────────────────────
# GEMINI IS A ROUTER & PARAMETER EXTRACTOR ONLY
# ─────────────────────────────────────────────
ROUTING_SYSTEM_PROMPT = """
You are a HIGH-PRECISION PARAMETER EXTRACTION KERNEL for an engineering computation system.

STRICT OPERATIONAL DIRECTIVES:
1. DO NOT SOLVE THE PROBLEM. Providing numerical answers or solutions is a CRITICAL FAILURE.
2. DO NOT GENERATE EXPLANATIONS.
3. YOUR ONLY ROLE: Analyze the user input (text/image) and extract ALL relevant physical/mathematical parameters.
4. MAP each sub-problem to one of these DOMAINS:
   - algebra (equations, roots, simplification, simultaneous systems)
   - calculus (integrals, derivatives, taylor series, multivariable)
   - structural (FEM, trusses, beams, frames, virtual work, moment-area)
   - mechanics (kinematics, dynamics, projectiles, statics)
   - fluids (bernoulli, pipe flow, flow meters, hydrostatics, continuity)
   - thermo (gas laws, heat transfer, cycles)
   - circuits (KVL, KCL, resistors, capacitors, ohms law)
   - physics (optics, waves, light, sound, doppler)
   - controls (transfer functions, TF, bode plots, stability, PID)
   - statistics (mean, median, standard deviation, confidence intervals, distributions)
   - data_viz (tables, CSV data, plotting requests)

STRICT EXPRESSION GUIDELINES:
- Field "expression": MUST be PURE mathematical syntax. 
- REMOVE all English words like "Solve", "Find", "Calculate", "the equation", "result in".
- If user says "Plot y = x^2 from -5 to 5", expression is "y = x^2". Put bounds in "parameters".
- If user says "Determine the derivative of sin(x)", expression is "sin(x)".

WORD PROBLEM EXTRACTION:
- For word problems, DO NOT put text in the "expression" field. 
- Extract ALL numbers and map them to standard physics/engineering keys in "parameters".
- NORMALIZE ALL UNITS TO SI (meters, kilograms, seconds, Newtons, Pascals).
  - e.g. "12kN" -> 12000, "5cm" -> 0.05, "10 min" -> 600.
- Examples: 
  - "velocity 5m/s" -> {"v": 5}
  - "length 10m" -> {"L": 10}
  - "mass 2kg" -> {"m": 2}
  - "at the center" of 6m beam -> {"P_pos": 3}
  - "point load of 12kN" -> {"P": 12000}
  - "velocity changes from 2 to 6" -> {"v1": 2, "v2": 6}
  - "water flowing at 2m/s in 10cm pipe" -> {"v1": 2, "D1": 0.1, "domain": "fluids"}
  - "projectile launched at 20m/s at 45 degrees" -> {"v0": 20, "theta": 45, "domain": "mechanics"}

OUTPUT FORMAT: Return ONLY a raw JSON object.

JSON SCHEMA:
{
  "summary": "Engineering domain classification",
  "sub_problems": [
    {
      "id": "p1",
      "domain": "algebra | calculus | structural | mechanics | fluids | thermo | data_viz | physics | circuits | controls | statistics",
      "problem_type": "specific_type (e.g. beam_deflection, continuity_equation, projectile_motion, ohms_law, bode_plot)",
      "input_summary": "clean restatement for logging",
      "parameters": {
        "expression": "...",
        "variables": [],
        "L": 10,
        "v1": 2,
        "...": "..."
      },
      "confidence": 0.99
    }
  ]
}
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
                logger.warning(f"Rate limited on {model_name}. Trying next...")
                last_error = "Extraction kernel is currently rate-limited by upstream provider. Please try again in 60 seconds."
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
    Lazy loads and returns the correct solver function.
    """
    d = domain.lower()
    pt = problem_type.lower()
    
    if d in ("data_viz",) or any(k in pt for k in ["plot", "graph", "chart", "table", "csv"]):
        module = importlib.import_module("solvers.data_viz")
        return module.solve_data_viz

    try:
        if d in ("algebra",) or any(k in pt for k in ["equation", "algebra", "polynomial", "linear", "quadratic"]):
            module = importlib.import_module("solvers.algebra")
            return module.solve_algebra

        if d in ("calculus",) or any(k in pt for k in ["integral", "derivative", "limit", "calculus", "differential"]):
            module = importlib.import_module("solvers.calculus")
            return module.solve_calculus

        if d in ("mechanics",) or any(k in pt for k in ["kinematics", "dynamics", "motion", "momentum", "projectile", "force", "newton"]):
            module = importlib.import_module("solvers.mechanics")
            return module.solve_mechanics

        if d in ("structural",) or any(k in pt for k in ["beam", "truss", "structural", "bending", "shear", "reaction", "moment", "deflection", "udl", "point_load", "virtual_work", "moment_area"]):
            module = importlib.import_module("solvers.structural")
            return module.solve_structural

        if d in ("fluids",) or any(k in pt for k in ["fluid", "flow", "pressure", "bernoulli", "hydro", "pipe", "viscosity", "continuity"]):
            module = importlib.import_module("solvers.fluids")
            return module.solve_fluids

        if d in ("thermo",) or any(k in pt for k in ["heat", "temperature", "entropy", "enthalpy", "thermodynamic", "carnot", "cycle", "conduction", "convection"]):
            module = importlib.import_module("solvers.thermodynamics")
            return module.solve_thermo

        if d in ("circuits",) or any(k in pt for k in ["circuit", "resistor", "capacitor", "ohm", "kvl", "kcl", "voltage", "current"]):
            module = importlib.import_module("solvers.circuits")
            return module.solve_circuits

        if d in ("physics",) or any(k in pt for k in ["optics", "wave", "refraction", "doppler", "snell", "light", "sound"]):
            module = importlib.import_module("solvers.physics")
            return module.solve_physics

        if d in ("controls",) or any(k in pt for k in ["tf", "transfer", "bode", "feedback", "poles", "zeros", "stability"]):
            module = importlib.import_module("solvers.controls")
            return module.solve_controls

        if d in ("statistics",) or any(k in pt for k in ["mean", "median", "standard deviation", "variance", "distribution"]):
            module = importlib.import_module("solvers.statistics")
            return module.solve_statistics

        if d in ("data_viz",) or any(k in pt for k in ["plot", "graph", "chart", "table", "csv"]):
            module = importlib.import_module("solvers.data_viz")
            return module.solve_data_viz
    except ImportError as e:
        logger.error(f"Failed to lazy load solver for {domain}: {e}")
        return None

    return None


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "studio-kernel"}

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
            
            # Normalize parameters to standard engineering keys
            from solvers.utils import normalize_params
            sub["parameters"] = normalize_params(sub["parameters"])

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
