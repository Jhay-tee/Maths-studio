from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import os
import json
import asyncio
import time
from google import genai
from google.genai import types
import base64
import logging
import importlib
import re
from solvers.utils import (
    normalize_params,
    apply_standard_defaults,
    merge_params,
    find_missing_params,
    parse_user_supplied_value,
    resolve_numeric_expressions,
    polish_final_answer,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
MAX_REQUEST_BYTES = int(os.environ.get("MAX_REQUEST_BYTES", 8 * 1024 * 1024))
MAX_CONCURRENT_SOLVES = int(os.environ.get("MAX_CONCURRENT_SOLVES", 6))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", 60))
RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", 24))
ROUTER_TIMEOUT_SECONDS = float(os.environ.get("ROUTER_TIMEOUT_SECONDS", 20))
SOLVE_TIMEOUT_SECONDS = float(os.environ.get("SOLVE_TIMEOUT_SECONDS", 45))
solve_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SOLVES)
request_windows = {}
request_windows_lock = asyncio.Lock()

@app.get("/health")
async def health():
    return {"status": "ok", "uptime": "running"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SafetyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_BYTES:
                    return JSONResponse(
                        {"error": "Request payload too large."},
                        status_code=413,
                    )
            except ValueError:
                pass

        now = time.monotonic()
        async with request_windows_lock:
            window = request_windows.get(client_ip, [])
            window = [stamp for stamp in window if now - stamp < RATE_LIMIT_WINDOW_SECONDS]
            if len(window) >= RATE_LIMIT_MAX_REQUESTS:
                return JSONResponse(
                    {"error": "Too many requests. Please slow down and try again shortly."},
                    status_code=429,
                )
            window.append(now)
            request_windows[client_ip] = window

        response = await call_next(request)
        response.headers["X-Studio-RateLimit-Limit"] = str(RATE_LIMIT_MAX_REQUESTS)
        response.headers["X-Studio-RateLimit-Window"] = str(RATE_LIMIT_WINDOW_SECONDS)
        response.headers["X-Studio-Max-Concurrent-Solves"] = str(MAX_CONCURRENT_SOLVES)
        return response


app.add_middleware(SafetyMiddleware)

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
   - calculus (integrals, derivatives, limits, differential equations, taylor series, multivariable, laplace, fourier)
   - structural (FEM, trusses, beams, frames, virtual work, moment-area)
   - mechanics (kinematics, dynamics, projectiles, statics, vibration, rotation)
   - fluids (bernoulli, pipe flow, flow meters, hydrostatics, continuity)
   - thermo (gas laws, heat transfer, cycles)
   - circuits (KVL, KCL, resistors, capacitors, ohms law)
   - physics (optics, waves, light, sound, doppler)
   - controls (transfer functions, TF, bode plots, stability, PID)
   - statistics (mean, median, standard deviation, confidence intervals, distributions)
   - data_viz (tables, CSV data, plotting requests, graphs, charts)
5. IF THE USER ASKS MULTIPLE QUESTIONS OR A QUESTION WITH MULTIPLE DISTINCT TASKS, SPLIT THEM INTO MULTIPLE sub_problems.
6. IF THE USER ASKS FOR BOTH A GRAPH AND AN ANALYSIS/SOLUTION, RETURN MULTIPLE sub_problems so one handles plotting and another handles solving.
7. FOR WORD PROBLEMS, extract numbers, units, relationships, and requested outputs. DO NOT pass natural-language sentences into the "expression" field.
8. FOR EMBEDDED CALCULATIONS, preserve the computable relation in parameters using simple symbolic/numeric syntax only.

STRICT EXPRESSION GUIDELINES:
- Field "expression": MUST be PURE mathematical syntax. 
- REMOVE all English words like "Solve", "Find", "Calculate", "the equation", "result in".
- If user says "Plot y = x^2 from -5 to 5", expression is "y = x^2". Put bounds in "parameters".
- If user says "Determine the derivative of sin(x)", expression is "sin(x)".
- NEVER place full word-problem text into "expression".
- NEVER put prose such as "minimum force to move the book" into "expression".
- Use explicit math like "2*x + y = 4", "sin(x)", "P/(A*E)", or "m*g".

WORD PROBLEM EXTRACTION:
- For word problems, DO NOT put the full text in the "expression" field. 
- Extract ALL numbers and map them to standard physics/engineering keys in "parameters".
- CONTEXT MATTERS:
  - Beam analysis keywords: "simply supported", "cantilever", "deflection", "slope", "point load", "udl" -> domain="structural".
  - Control systems keywords: "transfer function", "poles", "zeros", "bode plot", "frequency response", "step response" -> domain="controls".
  - Data viz keywords: "plot", "surface", "experimental data", "stress-strain" -> domain="data_viz".
- UNCERTAINTY EXTRACTION: If parameters have tolerances (e.g. "10 +/- 0.5m", "mass 5kg with 2% error"), extract the nominal value and the absolute uncertainty. 
  - Use suffix "_sigma" for uncertainty (e.g. "m": 10, "m_sigma": 0.5).
  - For percentage, convert to absolute (e.g. 5kg +/- 2% -> m=5, m_sigma=0.1).
- DO NOT fallback to "algebra" just because there is an unknown. Algebra implies PURE equation solving with no physical context.
- CHECK FOR IMPOSSIBILITIES: If the input describes something impossible (e.g. mass = -5kg), extract the parameters anyway, but the solvers will handle the error.
- SPLIT multi-part questions into separate items in `sub_problems` (e.g. "Find the force AND the work done").
- NORMALIZE ALL UNITS TO SI (meters, kilograms, seconds, Newtons, Pascals).
  - e.g. "12kN" -> 12000, "5cm" -> 0.05, "10 min" -> 600, "200 GPa" -> 2e11.
- Examples: 
  - "velocity 5m/s" -> {"v": 5}
  - "velocity 10 +/- 0.2 m/s" -> {"v": 10, "v_sigma": 0.2}
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

            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=ROUTING_SYSTEM_PROMPT,
                        temperature=0.1,  # Low temp = deterministic routing
                    ),
                ),
                timeout=ROUTER_TIMEOUT_SECONDS,
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
        except asyncio.TimeoutError:
            logger.warning(f"Model {model_name} timed out in router")
            last_error = "Routing timed out while extracting parameters."
            continue
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


def split_user_questions(user_input: str) -> list[str]:
    text = (user_input or "").strip()
    if not text:
        return []

    parts = [
        segment.strip(" \n\t-")
        for segment in re.split(r"\?\s+|\n{2,}", text)
        if segment.strip()
    ]
    return parts if len(parts) > 1 else [text]


def build_fallback_route(user_input: str) -> dict | None:
    text = (user_input or "").strip()
    lowered = text.lower()
    if not text:
        return None

    if any(keyword in lowered for keyword in ["plot", "graph"]) and "=" in text:
        equation_match = re.search(r"([A-Za-z0-9\s+\-*/^().=]+)", text)
        expression = equation_match.group(1).strip() if equation_match else text
        sub_problems = [
            {
                "id": "p1",
                "domain": "data_viz",
                "problem_type": "function_plot",
                "input_summary": text,
                "parameters": {"expression": expression},
                "confidence": 1.0,
            }
        ]
        if any(keyword in lowered for keyword in ["solve", "find", "intercept", "root", "gradient", "slope"]):
            sub_problems.append(
                {
                    "id": "p2",
                    "domain": "algebra",
                    "problem_type": "equation_solving",
                    "input_summary": text,
                    "parameters": {"expression": expression},
                    "confidence": 0.95,
                }
            )
        return {
            "summary": "Graph plotting request",
            "_model": "rule-based-route",
            "sub_problems": sub_problems,
        }

    if "=" in text and not any(keyword in lowered for keyword in ["plot", "graph"]):
        return {
            "summary": "Algebra equation solving request",
            "_model": "rule-based-route",
            "sub_problems": [
                {
                    "id": "p1",
                    "domain": "algebra",
                    "problem_type": "equation_solving",
                    "input_summary": text,
                    "parameters": {"expression": text},
                    "confidence": 1.0,
                }
            ],
        }

    if "deflection values" in lowered and "plot" in lowered:
        return {
            "summary": "Engineering data plotting request",
            "_model": "rule-based-route",
            "sub_problems": [
                {
                    "id": "p1",
                    "domain": "data_viz",
                    "problem_type": "plot_data",
                    "input_summary": text,
                    "parameters": {},
                    "confidence": 1.0,
                }
            ],
        }

    if any(keyword in lowered for keyword in ["plot", "graph"]) and re.search(r"\d", text):
        return {
            "summary": "Numeric plotting request",
            "_model": "rule-based-route",
            "sub_problems": [
                {
                    "id": "p1",
                    "domain": "data_viz",
                    "problem_type": "plot_data",
                    "input_summary": text,
                    "parameters": {},
                    "confidence": 0.95,
                }
            ],
        }

    if any(keyword in lowered for keyword in ["beam", "cantilever", "truss", "column", "deflection", "shear", "moment"]):
        sub_problems = [
            {
                "id": "p1",
                "domain": "structural",
                "problem_type": "structural_analysis",
                "input_summary": text,
                "parameters": {},
                "confidence": 0.95,
            }
        ]
        if "=" in text:
            sub_problems.append(
                {
                    "id": "p2",
                    "domain": "algebra",
                    "problem_type": "equation_solving",
                    "input_summary": text,
                    "parameters": {"expression": text},
                    "confidence": 0.8,
                }
            )
        return {
            "summary": "Structural analysis request",
            "_model": "rule-based-route",
            "sub_problems": sub_problems,
        }

    if any(keyword in lowered for keyword in ["book", "table", "friction", "normal force"]):
        return {
            "summary": "Statics and friction analysis",
            "_model": "rule-based-route",
            "sub_problems": [
                {
                    "id": "p1",
                    "domain": "mechanics",
                    "problem_type": "static_friction",
                    "input_summary": text,
                    "parameters": {},
                    "confidence": 0.98,
                }
            ],
        }

    if any(keyword in lowered for keyword in ["pressure at the bottom", "bubble", "vegetable oil", "hole at the bottom", "hydrostatic"]):
        return {
            "summary": "Hydrostatics concept question",
            "_model": "rule-based-route",
            "sub_problems": [
                {
                    "id": "p1",
                    "domain": "fluids",
                    "problem_type": "hydrostatics",
                    "input_summary": text,
                    "parameters": {},
                    "confidence": 0.98,
                }
            ],
        }

    return None


def build_multi_question_route(user_input: str) -> dict | None:
    parts = split_user_questions(user_input)
    if len(parts) <= 1:
        return None

    sub_problems = []
    for index, part in enumerate(parts, start=1):
        route = build_fallback_route(part)
        if route is None:
            return None
        for sub in route.get("sub_problems", []):
            copy = dict(sub)
            copy["id"] = f"p{len(sub_problems) + 1}"
            copy["input_summary"] = part
            sub_problems.append(copy)

    if not sub_problems:
        return None

    return {
        "summary": "Multi-question request",
        "_model": "rule-based-route",
        "sub_problems": sub_problems,
    }


def sanitize_routing_result(routing: dict, user_input: str, input_type: str) -> dict:
    if input_type != "text":
        return routing

    sub_problems = routing.get("sub_problems") or []
    
    # Check if Gemini provided a confident engineering/physics classification
    # If Gemini failed or was extremely non-specific, try the rule-based fallbacks
    is_vague = not sub_problems or all(p.get("confidence", 0) < 0.3 for p in sub_problems)
    
    if is_vague:
        multi_route = build_multi_question_route(user_input)
        if multi_route is not None:
            return multi_route

        fallback = build_fallback_route(user_input)
        if fallback:
            return fallback

    return routing


def clean_sub_problem(domain: str, sub: dict) -> dict:
    cleaned = dict(sub)
    params = dict(cleaned.get("parameters") or {})
    expr = params.get("expression")

    if isinstance(expr, str):
        expr_text = expr.strip()
        word_count = len(re.findall(r"[A-Za-z]+", expr_text))
        has_sentence_markers = any(token in expr_text.lower() for token in ["what", "why", "when", "if ", "minimum", "force needed", "problem", "value of"])
        if domain not in {"algebra", "calculus", "data_viz"} and (word_count > 8 or has_sentence_markers):
            params.pop("expression", None)

    cleaned["parameters"] = params
    return cleaned


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
    acquired_slot = False
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

    try:
        await asyncio.wait_for(solve_semaphore.acquire(), timeout=2.0)
        acquired_slot = True
    except asyncio.TimeoutError:
        async def _busy():
            yield make_error_event("Studio kernel is busy. Please retry in a few seconds.")
        return StreamingResponse(_busy(), media_type="text/event-stream")

    async def event_generator():
        try:
            # ── Step 1: Route via Gemini (classify only) ──
            if input_type == "data":
                yield make_event({
                    "type": "step",
                    "content": "Studio Kernel: Loading dataset and preparing visualization pipeline...",
                })
                routing = {
                    "summary": "Dataset visualization request",
                    "_model": "direct-data-route",
                    "sub_problems": [
                        {
                            "id": "p1",
                            "domain": "data_viz",
                            "problem_type": "table_plot",
                            "input_summary": raw_data.get("filename", "Uploaded dataset"),
                            "parameters": {
                                "table_data": user_input,
                            },
                            "confidence": 1.0,
                        }
                    ],
                }
            else:
                yield make_event({
                    "type": "step",
                    "content": "Studio Kernel: Classifying and extracting parameters...",
                })

                routing = await route_input(user_input, is_image, history)
                routing = sanitize_routing_result(routing, user_input, input_type)

            if "error" in routing:
                yield make_error_event("Routing Failed: " + routing["error"])
                return

            sub_problems = routing.get("sub_problems", [])

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

            for idx, sub in enumerate(sub_problems):
                domain = sub.get("domain", "unknown").lower()
                problem_type = sub.get("problem_type", "unknown").lower()
                problem_id = sub.get("id", f"p{idx}")
                confidence = sub.get("confidence", 0.0)
                sub = clean_sub_problem(domain, sub)

                yield make_event({
                    "type": "step",
                    "content": f"Dispatching Sub-problem {idx + 1}: [{domain}] {problem_type} (confidence: {confidence:.0%})",
                })

                if "parameters" not in sub:
                    sub["parameters"] = {}

                supplemental_params = raw_data.get("supplemental_params", {})
                parsed_supplemental = {
                    key: parse_user_supplied_value(value)
                    for key, value in supplemental_params.items()
                }
                sub["parameters"] = resolve_numeric_expressions(
                    apply_standard_defaults(
                        merge_params(sub["parameters"], parsed_supplemental)
                    )
                )
                if raw_data.get("plot_config"):
                    sub["parameters"]["plot_config"] = raw_data.get("plot_config", {})

                sub["raw_query"] = sub.get("input_summary", user_input)
                sub["topic"] = domain
                sub["requested_method"] = (
                    sub["parameters"].get("method")
                    or raw_data.get("method")
                    or None
                )

                missing = find_missing_params(
                    domain,
                    problem_type,
                    sub["parameters"],
                    sub["raw_query"],
                )
                if missing:
                    yield make_event({
                        "type": "needs_parameters",
                        "problem_id": problem_id,
                        "message": "Parameter is not specified.",
                        "missing_params": missing,
                        "problem_description": sub.get("input_summary", user_input),
                    })
                    return

                solver_fn = select_solver(domain, problem_type)

                if not solver_fn:
                    yield make_event({
                        "type": "final",
                        "answer": f"No solver available for domain '{domain}' / type '{problem_type}'.",
                        "problem_id": problem_id,
                    })
                    continue

                try:
                    async with asyncio.timeout(SOLVE_TIMEOUT_SECONDS):
                        async for chunk in solver_fn(sub):
                            chunk["problem_id"] = problem_id

                            if len(sub_problems) > 1 and chunk.get("type") == "final":
                                summary = sub.get("input_summary", f"Problem {idx + 1}")
                                chunk["answer"] = f"### Problem {idx + 1}\n{summary}\n\n{chunk.get('answer', '')}"

                            if chunk.get("type") == "final":
                                chunk["answer"] = polish_final_answer(
                                    chunk.get("answer", ""),
                                    domain=domain,
                                    problem_type=problem_type,
                                )

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
                except TimeoutError:
                    logger.warning(f"Solver timeout in sub-problem {idx} ({domain}/{problem_type})")
                    yield make_error_event(
                        f"Solver Timeout [{domain}]: computation exceeded the safe time limit.",
                        problem_id,
                    )
                except Exception as e:
                    logger.error(f"Solver error in sub-problem {idx} ({domain}/{problem_type}): {e}")
                    yield make_error_event(
                        f"Solver Error [{domain}]: {str(e)}", problem_id
                    )
        finally:
            if acquired_slot:
                solve_semaphore.release()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9999)
