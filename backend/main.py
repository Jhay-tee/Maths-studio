from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import asyncio
import google.generativeai as genai
import base64
import logging

# Configure logging
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

# Configure Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=SYSTEM_INSTRUCTION
            )
            
            contents = []
            if history:
                for msg in history:
                    contents.append(msg) # Standard LangChain/Gemini history format expected
            
            prompt = "Analyze these engineering problems. If multiple exist, separate them. If options are provided, extract them clearly."
            
            if is_image:
                if "," in input_data:
                    input_data = input_data.split(",")[1]
                image_data = base64.b64decode(input_data)
                contents.append({'mime_type': 'image/jpeg', 'data': image_data})
                contents.append(prompt)
            else:
                contents.append(f"User Input: {input_data}\n\n{prompt}")
                
            response = await asyncio.to_thread(model.generate_content, contents)
            
            text = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(text)
            data["_model"] = model_name
            return data
        except Exception as e:
            logger.warning(f"Model {model_name} failed: {e}")
            last_error = str(e)
            if "429" in last_error or "quota" in last_error.lower():
                continue
            break
            
    return {"error": last_error or "Extraction failed"}

@app.post("/solve")
async def solve(request: Request):
    raw_data = await request.json()
    user_input = raw_data.get("input")
    input_type = raw_data.get("type", "text")
    history = raw_data.get("history", [])
    is_image = input_type == "image"
    
    async def event_generator():
        yield f"data: {json.dumps({'type': 'step', 'content': 'Studio Kernel: Analyzing input context...'})}\n\n"
        
        # 1. Extraction Phase
        data = await extract_parameters(user_input, is_image, history)
        
        if "error" in data:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Extraction Failed: {data['error']}'})}\n\n"
            return

        sub_problems = data.get("sub_problems", [])
        if not sub_problems and "topic" in data:
            # Migration path for older schema if Gemini returns single object
            sub_problems = [data]

        yield f"data: {json.dumps({'type': 'meta', 'summary': data.get('summary', 'Processing multiple queries')})}\n\n"
        
        # 2. Solving Phase iterate through all sub problems
        for idx, sub in enumerate(sub_problems):
            topic = sub.get("topic", "unknown").lower()
            problem_id = sub.get("id", f"p{idx}")
            
            yield f"data: {json.dumps({'type': 'step', 'content': f'Solving Sub-problem {idx + 1}: {topic.capitalize()}'})}\n\n"
            
            if "units" in sub:
                yield f"data: {json.dumps({'type': 'units', 'data': sub['units'], 'problem_id': problem_id})}\n\n"

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
                        # Append metadata about which problem this chunk belongs to
                        chunk["problem_id"] = problem_id
                        
                        # Handle Option Matching at final step if options exist
                        if chunk["type"] == "final" and sub.get("options"):
                            ans_text = chunk["answer"]
                            options = sub["options"]
                            # Simple heuristic for option matching
                            # In a production app, we'd use Gemini again or more robust regex
                            matched = False
                            for opt in options:
                                if str(opt.get("label")).lower() in ans_text.lower() or str(opt.get("val")) in ans_text:
                                    chunk["answer"] += f"\n\n**Correct Option: {opt['label']}**"
                                    matched = True
                                    break
                            if not matched:
                                chunk["answer"] += f"\n\n**Note: No corresponding option matches exactly.**"

                        yield f"data: {json.dumps(chunk)}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'final', 'answer': f'Computed generic results for {topic}.', 'problem_id': problem_id})}\n\n"
            except Exception as e:
                logger.error(f"Solver error in sub-problem {idx}: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': f'Solver Error ({topic}): {str(e)}', 'problem_id': problem_id})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9999)
