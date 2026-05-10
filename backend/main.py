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

SYSTEM_INSTRUCTION = """
  You are an "Engineering Parameter Extraction & Solution Orchestrator".
  Your job is to:
  1. Read the user's input (Text/Image) and any provided chat history.
  2. IDENTIFY ALL PROBLEMS: If the user asks multiple questions, handle each.
  3. CLASSIFY & EXTRACT: For each sub-problem, detect topic, extract parameters (normalize to SI), and identify any provided "options" (A, B, C, D).
  4. ORCHESTRATE:
     - Return an array of "sub_problems".
     - For each, provide a "topic", "summary", "units", "options" (optional), and "constraints".
  5. OPTION MATCHING:
     - If "options" are present, the solver will later produce a value. You must ensure the solver knows to compare its final value with these options.
  6. OUTLIER DETECTION:
     - Flag unusual values (e.g., density of water != 1000).
  7. Output ONLY valid JSON in this format:
     {
       "summary": "overall summary",
       "sub_problems": [
         {
           "id": "p1",
           "topic": "algebra|fluids|thermo|...",
           "summary": "...",
           "units": [...],
           "options": [{"label": "A", "val": 10.5}, ...],
           "raw_query": "..."
         }
       ]
     }
"""


async def extract_parameters(input_data: str, is_image: bool, history: list = None):
    last_error = None
    for model_name in MODELS:
        try:
            contents = []

            if history:
                for msg in history:
                    contents.append(msg)

            prompt = "Analyze these engineering problems. If multiple exist, separate them. If options are provided, extract them clearly."

            if is_image:
                if "," in input_data:
                    input_data = input_data.split(",")[1]
                image_bytes = base64.b64decode(input_data)
                contents.append(
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                )
                contents.append(prompt)
            else:
                contents.append(f"User Input: {input_data}\n\n{prompt}")

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                ),
            )

            text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(text)
            data["_model"] = model_name
            return data

        except json.JSONDecodeError as e:
            logger.error(f"Model {model_name} returned invalid JSON: {e}")
            last_error = f"Invalid JSON from model: {str(e)}"
            break
        except Exception as e:
            logger.warning(f"Model {model_name} failed: {e}")
            last_error = str(e)
            if "429" in last_error or "quota" in last_error.lower():
                continue
            break

    return {"error": last_error or "Extraction failed"}


def make_error_event(message: str, problem_id: str = None) -> str:
    """Helper to safely serialize error SSE events — avoids nested f-string quote conflicts."""
    payload = {"type": "error", "message": message}
    if problem_id is not None:
        payload["problem_id"] = problem_id
    return f"data: {json.dumps(payload)}\n\n"


def make_event(data: dict) -> str:
    """Helper to safely serialize any SSE event."""
    return f"data: {json.dumps(data)}\n\n"


@app.post("/solve")
async def solve(request: Request):
    try:
        raw_data = await request.json()
    except Exception:
        async def bad_request():
            yield make_error_event("Invalid JSON in request body")
        return StreamingResponse(bad_request(), media_type="text/event-stream")

    user_input = raw_data.get("input")
    input_type = raw_data.get("type", "text")
    history = raw_data.get("history", [])
    is_image = input_type == "image"

    if not user_input:
        async def missing_input():
            yield make_error_event("No input provided")
        return StreamingResponse(missing_input(), media_type="text/event-stream")

    async def event_generator():
        yield make_event({"type": "step", "content": "Studio Kernel: Analyzing input context..."})

        # 1. Extraction phase
        data = await extract_parameters(user_input, is_image, history)

        if "error" in data:
            yield make_error_event("Extraction Failed: " + data["error"])
            return

        sub_problems = data.get("sub_problems", [])
        if not sub_problems and "topic" in data:
            # Migration path: Gemini returned single object instead of array
            sub_problems = [data]

        if not sub_problems:
            yield make_error_event("No sub-problems could be extracted from the input")
            return

        yield make_event({
            "type": "meta",
            "summary": data.get("summary", "Processing multiple queries"),
        })

        # 2. Solving phase
        for idx, sub in enumerate(sub_problems):
            topic = sub.get("topic", "unknown").lower()
            problem_id = sub.get("id", f"p{idx}")

            yield make_event({
                "type": "step",
                "content": f"Solving Sub-problem {idx + 1}: {topic.capitalize()}",
            })

            if "units" in sub:
                yield make_event({
                    "type": "units",
                    "data": sub["units"],
                    "problem_id": problem_id,
                })

            try:
                solver_stream = None

                if any(t in topic for t in ["calculus", "integral", "derivative", "limit"]):
                    solver_stream = solve_calculus(sub)
                elif any(t in topic for t in ["algebra", "math", "equation"]):
                    solver_stream = solve_algebra(sub)
                elif any(t in topic for t in ["mechanics", "kinematics", "dynamics", "motion"]):
                    solver_stream = solve_mechanics(sub)
                elif any(t in topic for t in ["structural", "beam", "truss", "stress", "strain"]):
                    solver_stream = solve_structural(sub)
                elif any(t in topic for t in ["fluids", "fluid", "pressure", "hydro", "flow"]):
                    solver_stream = solve_fluids(sub)
                elif any(t in topic for t in ["thermo", "heat", "temperature", "entropy", "enthalpy"]):
                    solver_stream = solve_thermo(sub)

                if solver_stream:
                    async for chunk in solver_stream:
                        chunk["problem_id"] = problem_id

                        # Option matching on final chunk
                        if chunk.get("type") == "final" and sub.get("options"):
                            ans_text = str(chunk.get("answer", ""))
                            options = sub["options"]
                            matched = False
                            for opt in options:
                                opt_label = str(opt.get("label", "")).lower()
                                opt_val = str(opt.get("val", ""))
                                if opt_label in ans_text.lower() or opt_val in ans_text:
                                    chunk["answer"] = ans_text + f"\n\n**Correct Option: {opt['label']}**"
                                    matched = True
                                    break
                            if not matched:
                                chunk["answer"] = ans_text + "\n\n**Note: No corresponding option matches exactly.**"

                        yield make_event(chunk)
                else:
                    yield make_event({
                        "type": "final",
                        "answer": f"No solver available for topic: {topic}",
                        "problem_id": problem_id,
                    })

            except Exception as e:
                logger.error(f"Solver error in sub-problem {idx} ({topic}): {e}")
                yield make_error_event(f"Solver Error ({topic}): {str(e)}", problem_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9999)
