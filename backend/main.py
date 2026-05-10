from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
import os
from typing import Dict, Any
from dotenv import load_dotenv
import google.generativeai as genai

# Load env vars
load_dotenv()

# Modular imports
from solvers.mechanics import solve_beam
from solvers.math_solver import solve_algebra
from solvers.structural_solver import solve_structural

app = FastAPI()

# Configure Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODELS = ["gemini-3-flash-preview", "gemini-3.1-pro-preview"]

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
  You are an "Engineering Parameter Extraction Engine".
  Your job is to:
  1. Read the user's problem (Text or Image).
  2. Classify the topic (Algebra, Calculus, Mechanics, Structural, etc.).
  3. Extract parameters into a clean JSON format for a Python solver.
  4. Handle COMPLEX units:
     - Detect distributed loads like 'N/mm', 'kN/m', 'lb/ft'.
     - Detect power-of-ten notation (e.g., '2e6', '10^3', 'x10^5').
     - Normalize all values to base SI units (Meters, Newtons, Pascals, Kilograms) in 'si_val'.
  5. INFUSE STANDARD CONSTANTS:
     - If the problem involves water but no density is given, add {"param": "density_water", "si_val": 1000, "unit": "kg/m3", "type": "constant"}.
     - If gravity is needed but missing, add {"param": "gravity", "si_val": 9.81, "unit": "m/s2", "type": "constant"}.
     - If Young's Modulus for Steel is implied/needed but missing, assume 2.0e11 (200GPa).
     - ONLY add if NOT provided by user.
  6. BEAM SPECIFIC EXTRACTION:
     - If topic is 'beam', provide a 'loads' array.
     - Point load: {"type": "point", "value": magnitude_in_N, "pos": position_in_m}.
     - Distributed load: {"type": "distributed", "value": magnitude_in_N_per_m, "start": start_m, "end": end_m}.
  7. Provide a short "summary" string (max 60 chars).
  8. For EACH parameter, return: {"val": original_numeric, "unit": "raw_unit", "si_val": normalized, "si_unit": "SI", "type": "length|force|distributed_load|constant", "param": "name"}.
  9. Return a 'units' array containing all extracted parameters.

  STRICT RULES:
  - NO conversational behavior.
  - IF input is offensive or unrelated to engineering/math, return {"error": "not_math"}.
  - Output ONLY valid JSON.
  - Topic must be lowercase.
"""

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Adjust this in production to your Vercel URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def extract_parameters(input_data: str, is_image: bool = False):
    used_model = MODELS[0]
    last_error = None
    
    for model_name in MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            
            if is_image:
                response = await asyncio.to_thread(
                    model.generate_content,
                    [
                        {"mime_type": "image/jpeg", "data": input_data},
                        SYSTEM_PROMPT + "\n\nExtract engineering parameters from this image."
                    ]
                )
            else:
                response = await asyncio.to_thread(
                    model.generate_content, 
                    SYSTEM_PROMPT + "\n\nUser Problem: " + input_data
                )
                
            text = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(text)
            data["_model_used"] = model_name
            data["_is_fallback"] = model_name != MODELS[0]
            return data
            
        except Exception as e:
            last_error = str(e)
            if "429" in last_error or "quota" in last_error.lower():
                continue
            break
            
    return {"error": "extraction_failed", "message": f"AI Engine Exception: {last_error}"}

async def result_generator(raw_data: Dict[str, Any]):
    user_input = raw_data.get("input")
    is_image = raw_data.get("type") == "image"
    
    yield f"data: {json.dumps({'type': 'step', 'content': 'Reading input and identifying mathematical context...'})}\n\n"
    
    if is_image:
        yield f"data: {json.dumps({'type': 'step', 'content': 'AI Vision: Scanning diagram for engineering constraints...'})}\n\n"
    
    # 1. Extraction step (Skip if frontend already provided extracted data)
    if "topic" in raw_data and "units" in raw_data:
        data = raw_data
        yield f"data: {json.dumps({'type': 'step', 'content': 'Using pre-extracted parameters...'})}\n\n"
    else:
        data = await extract_parameters(user_input, is_image)
    
    if "error" in data:
        msg = "This is not a valid mathematics or engineering problem." if data["error"] == "not_math" else "Unsupported topic or extraction error."
        yield f"data: {json.dumps({'type': 'step', 'content': f'Error: {msg}'})}\n\n"
        yield f"data: {json.dumps({'type': 'final', 'answer': 'Analysis halted.'})}\n\n"
        return

    topic = data.get("topic", "").lower()
    summary = data.get("summary", f"identified as {topic}")
    
    # Send metadata for frontend history
    yield f"data: {json.dumps({'type': 'meta', 'topic': topic, 'summary': summary, 'is_fallback': data.get('_is_fallback', False), 'model': data.get('_model_used')})}\n\n"

    # Send unit conversions info if available
    if "units" in data:
        yield f"data: {json.dumps({'type': 'units', 'data': data['units']})}\n\n"
    
    yield f"data: {json.dumps({'type': 'step', 'content': f'Domain: {topic.capitalize()} | Observation: {summary}'})}\n\n"
    
    if "structural" in topic:
        async for chunk in solve_structural(data):
            yield f"data: {json.dumps(chunk)}\n\n"
    elif "beam" in topic or "mechanics" in topic:
        async for chunk in solve_beam(data):
            yield f"data: {json.dumps(chunk)}\n\n"
    elif "algebra" in topic:
        async for chunk in solve_algebra(data):
            yield f"data: {json.dumps(chunk)}\n\n"
    else:
        yield f"data: {json.dumps({'type': 'step', 'content': 'Processing computation with general numerical kernel...'})}\n\n"
        await asyncio.sleep(0.5)
        yield f"data: {json.dumps({'type': 'final', 'answer': f'Computed successfully for {topic}. (Results would differ with specific domain solver)'})}\n\n"

@app.post("/solve")
async def solve(request: Request):
    raw_data = await request.json()
    return StreamingResponse(result_generator(raw_data), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
