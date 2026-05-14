"""
main.py  —  Engineering Computation Studio
FastAPI backend with two-layer routing and student-friendly responses.

Routing pipeline
────────────────
1. Layer 1  router.fast_classify()     deterministic, zero I/O, O(n_tokens)
2. Layer 2  Gemini parameter extractor called with domain already locked
   └─ L1 uncertain → Gemini does classification + extraction together

Gemini roles
────────────
• Parameter extractor  (always)
• Human-readable explainer  (always — wraps solver output in plain English)
• Full classifier  (only when L1 is uncertain)

Student-friendly design
────────────────────────
• Friendly error messages that suggest what to check
• Step outputs only shown when they contain real computed values
• Final answers use plain English + maths, not just raw numbers
• "Did you mean…?" hint when domain is ambiguous
"""

from __future__ import annotations

import asyncio
import base64
import importlib
import json
import logging
import os
import re
import time
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware

from google import genai
from google.genai import types

from router import fast_classify, ClassificationResult
from solvers.utils import (
    apply_standard_defaults,
    find_missing_params,
    merge_params,
    normalize_params,
    parse_user_supplied_value,
    polish_final_answer,
    resolve_numeric_expressions,
)

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

MAX_REQUEST_BYTES         = int(os.environ.get("MAX_REQUEST_BYTES",         8 * 1024 * 1024))
MAX_CONCURRENT_SOLVES     = int(os.environ.get("MAX_CONCURRENT_SOLVES",     6))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", 60))
RATE_LIMIT_MAX_REQUESTS   = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS",   24))
ROUTER_TIMEOUT_SECONDS    = float(os.environ.get("ROUTER_TIMEOUT_SECONDS",  20.0))
SOLVE_TIMEOUT_SECONDS     = float(os.environ.get("SOLVE_TIMEOUT_SECONDS",   45.0))

# ─────────────────────────────────────────────────────────────────────────────
# App + shared state
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Engineering Studio Kernel")

solve_semaphore       = asyncio.Semaphore(MAX_CONCURRENT_SOLVES)
request_windows: dict[str, list[float]] = {}
request_windows_lock  = asyncio.Lock()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
gemini_client  = genai.Client(api_key=GEMINI_API_KEY)

GEMINI_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

# ─────────────────────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


class SafetyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"

        # Payload size
        cl = request.headers.get("content-length")
        if cl:
            try:
                if int(cl) > MAX_REQUEST_BYTES:
                    return JSONResponse({"error": "Request payload too large."}, status_code=413)
            except ValueError:
                pass

        # Rate limiting
        is_sse = (
            request.url.path == "/api/compute/solve"
            and "text/event-stream" in request.headers.get("accept", "").lower()
        )
        limit = (
            int(os.environ.get("RATE_LIMIT_MAX_REQUESTS_STREAM",
                               str(RATE_LIMIT_MAX_REQUESTS * 2)))
            if is_sse else RATE_LIMIT_MAX_REQUESTS
        )
        now = time.monotonic()
        async with request_windows_lock:
            window = [t for t in request_windows.get(client_ip, [])
                      if now - t < RATE_LIMIT_WINDOW_SECONDS]
            if len(window) >= limit:
                msg = "Too many requests — please wait a moment and try again."
                if is_sse:
                    async def _rl():
                        yield _err(msg)
                    return StreamingResponse(_rl(), media_type="text/event-stream", status_code=429)
                return JSONResponse({"error": msg}, status_code=429)
            window.append(now)
            request_windows[client_ip] = window

        resp = await call_next(request)
        resp.headers["X-RateLimit-Limit"]  = str(limit)
        resp.headers["X-RateLimit-Window"] = str(RATE_LIMIT_WINDOW_SECONDS)
        return resp


app.add_middleware(SafetyMiddleware)


# ─────────────────────────────────────────────────────────────────────────────
# SSE helpers
# ─────────────────────────────────────────────────────────────────────────────

def _evt(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"

def _err(message: str, problem_id: str | None = None) -> str:
    p: dict = {"type": "error", "message": message}
    if problem_id:
        p["problem_id"] = problem_id
    return f"data: {json.dumps(p)}\n\n"

def _sse(gen) -> StreamingResponse:
    r = StreamingResponse(gen, media_type="text/event-stream")
    r.headers["Access-Control-Allow-Origin"]  = "*"
    r.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    r.headers["Access-Control-Allow-Headers"] = "Content-Type"
    r.headers["Cache-Control"]                = "no-cache"
    r.headers["Connection"]                   = "keep-alive"
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Gemini prompts
# ─────────────────────────────────────────────────────────────────────────────

# ── Prompt A: parameter extraction (domain already known from L1) ────────────
_EXTRACT_PROMPT = """
You are a parameter extraction assistant for an engineering computation engine.

The domain has already been identified as: {domain}

YOUR ONLY JOBS:
1. Extract every numerical parameter from the user's input.
2. Identify the specific problem type within that domain.
3. Return ONLY a raw JSON object — no markdown, no explanation, no preamble.

EXTRACTION RULES:
- Normalise ALL values to SI units:
    kN → ×1000  |  cm → ÷100  |  mm → ÷1000  |  GPa → ×1e9
    kPa → ×1e3  |  minutes → ×60  |  hours → ×3600
    °C in a formula context (ideal gas etc.) → add 273.15
- For tolerances like "10 ± 0.5 m" or "5 kg with 2% error":
    nominal → key as-is  (e.g. "m": 5)
    absolute sigma → key + "_sigma"  (e.g. "m_sigma": 0.1)
- The "expression" field must contain ONLY pure math syntax.
  No English words. Remove "Solve", "Find", "Calculate", "the equation", etc.
- For word problems, DO NOT put the problem sentence in "expression".
  Extract numbers into named keys instead.
- Split multi-part questions into separate items in sub_problems.
- DO NOT SOLVE the problem. DO NOT provide numerical answers.

OUTPUT (return ONLY this JSON, nothing else):
{
  "sub_problems": [
    {
      "id": "p1",
      "problem_type": "<specific type e.g. projectile_motion>",
      "input_summary": "<clean one-line restatement of the problem>",
      "parameters": {
        "expression": "<pure math only, or omit>",
        "<param_key>": <numeric_value>,
        ...
      },
      "confidence": 0.97
    }
  ]
}
"""

# ── Prompt B: full classification + extraction (L1 uncertain) ────────────────
_CLASSIFY_AND_EXTRACT_PROMPT = """
You are a classification and parameter extraction assistant for an engineering
computation engine.

AVAILABLE DOMAINS:
  algebra      — equations, roots, factorisation, simultaneous systems
  calculus     — derivatives, integrals, limits, ODEs, series, transforms
  structural   — beams, trusses, deflection, bending moment, stress/strain
  mechanics    — kinematics, dynamics, projectile, friction, energy, vibration
  fluids       — Bernoulli, pipe flow, hydrostatics, Reynolds number
  thermo       — gas laws, heat transfer, thermodynamic cycles
  circuits     — Ohm's law, KVL/KCL, RC/RL, Thevenin, Norton
  physics      — optics, waves, Doppler, refraction, modern physics
  controls     — transfer functions, Bode plots, PID, stability
  statistics   — mean/std/variance, hypothesis tests, regression
  data_viz     — plotting, graphing, charting any function or data

YOUR JOBS:
1. Identify the correct domain from the list above.
2. Extract all numerical parameters in SI units.
3. Return ONLY a raw JSON object — no markdown, no explanation.

Same extraction rules as before:
- Normalise to SI.
- Tolerances → _sigma suffix.
- expression = pure math only.
- Do NOT solve.

OUTPUT (return ONLY this JSON):
{
  "sub_problems": [
    {
      "id": "p1",
      "domain": "<one of the listed domains>",
      "problem_type": "<specific type>",
      "input_summary": "<clean one-line restatement>",
      "parameters": {
        "expression": "<pure math or omit>",
        "<key>": <value>,
        ...
      },
      "confidence": 0.97
    }
  ]
}
"""

# ── Prompt C: student-friendly explanation wrapper ───────────────────────────
_EXPLAIN_PROMPT = """
You are a friendly engineering tutor helping a student understand a solution.

The computation engine has already solved the problem and produced a raw result.
Your job is to rewrite it in clear, encouraging language that a first or
second-year engineering student can follow.

RULES:
1. Keep ALL numerical values EXACTLY as given — do not recalculate or alter them.
2. Walk through the key steps in plain English before giving the final answer.
3. Explain briefly WHY each formula is used (one sentence is enough).
4. Use simple LaTeX math inline ($...$) for equations.
5. End with a short "What this means in practice" sentence.
6. Keep a warm, encouraging tone — like a helpful senior student explaining
   to a classmate, not a textbook.
7. Do NOT add unsolicited warnings, disclaimers, or safety notices.
8. Keep it concise — no more than what is needed to understand the answer.

PROBLEM SUMMARY: {input_summary}

RAW SOLVER OUTPUT:
{raw_answer}

Rewrite this now in your friendly tutor style.
"""


# ─────────────────────────────────────────────────────────────────────────────
# History conversion
# ─────────────────────────────────────────────────────────────────────────────

def _history_to_contents(history: list) -> list:
    out = []
    for msg in history:
        role    = "model" if msg.get("role") == "assistant" else "user"
        content = msg.get("content", "").strip()
        if content:
            out.append(types.Content(role=role, parts=[types.Part.from_text(text=content)]))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Gemini caller  (shared retry logic)
# ─────────────────────────────────────────────────────────────────────────────

async def _gemini_call(
    system_prompt: str,
    user_message:  str,
    history:       list | None = None,
    image_b64:     str  | None = None,
    temperature:   float       = 0.05,
) -> str:
    """
    Call Gemini with retry across model list.
    Returns the raw text response.
    Raises RuntimeError on total failure.
    """
    contents = _history_to_contents(history or [])

    if image_b64:
        raw = image_b64.split(",")[1] if "," in image_b64 else image_b64
        contents.append(types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(data=base64.b64decode(raw), mime_type="image/jpeg"),
                types.Part.from_text(text=user_message),
            ],
        ))
    else:
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_message)],
        ))

    last_err = "Unknown error"
    for model in GEMINI_MODELS:
        try:
            resp = await asyncio.wait_for(
                asyncio.to_thread(
                    gemini_client.models.generate_content,
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                    ),
                ),
                timeout=ROUTER_TIMEOUT_SECONDS,
            )
            return resp.text

        except asyncio.TimeoutError:
            last_err = "Gemini timed out"
            continue
        except Exception as exc:
            last_err = str(exc)
            if "429" in last_err or "quota" in last_err.lower():
                continue
            break

    raise RuntimeError(last_err)


# ─────────────────────────────────────────────────────────────────────────────
# Routing orchestrator
# ─────────────────────────────────────────────────────────────────────────────

async def route_and_extract(
    user_input: str,
    is_image:   bool,
    history:    list,
) -> dict:
    """
    Returns a standard routing dict:
    {
        "sub_problems": [ { "id", "domain", "problem_type",
                            "input_summary", "parameters", "confidence" } ]
    }
    """

    # Images always skip L1 (can't keyword-match pixels)
    if is_image:
        raw = await _gemini_call(
            system_prompt=_CLASSIFY_AND_EXTRACT_PROMPT,
            user_message="Classify and extract parameters from this image. Return only JSON.",
            history=history,
            image_b64=user_input,
        )
        return _parse_gemini_json(raw, fallback_domain="unknown")

    # ── Layer 1 ──────────────────────────────────────────────────────────────
    l1 = fast_classify(user_input)

    if l1 is not None:
        logger.info(
            f"L1 → domain={l1.domain}  type={l1.problem_type}  "
            f"conf={l1.confidence}  signals={l1.matched_signals}"
        )
        # L1 decided domain; Gemini only extracts parameters
        prompt = _EXTRACT_PROMPT.format(domain=l1.domain)
        try:
            raw = await _gemini_call(
                system_prompt=prompt,
                user_message=f"Extract parameters.\n\nInput: {user_input}",
                history=history,
            )
            routing = _parse_gemini_json(raw, fallback_domain=l1.domain)
            # L1 domain is authoritative — Gemini cannot override it
            for sp in routing.get("sub_problems", []):
                sp["domain"] = l1.domain
                if sp.get("confidence", 0) < l1.confidence:
                    sp["confidence"] = l1.confidence
            return routing

        except Exception as exc:
            logger.warning(f"Gemini extraction failed after L1: {exc}. Using L1 skeleton.")
            return {
                "sub_problems": [{
                    "id":            "p1",
                    "domain":        l1.domain,
                    "problem_type":  l1.problem_type,
                    "input_summary": user_input,
                    "parameters":    {},
                    "confidence":    l1.confidence,
                }]
            }

    # ── Layer 2: L1 uncertain — Gemini classifies + extracts ─────────────────
    logger.info("L1 uncertain — escalating to Gemini full classification")
    try:
        raw = await _gemini_call(
            system_prompt=_CLASSIFY_AND_EXTRACT_PROMPT,
            user_message=f"Classify and extract parameters. Return only JSON.\n\nInput: {user_input}",
            history=history,
        )
        return _parse_gemini_json(raw, fallback_domain="unknown")
    except Exception as exc:
        return {"error": str(exc)}


def _parse_gemini_json(raw: str, fallback_domain: str) -> dict:
    """Parse Gemini JSON response, tolerating markdown fences."""
    text = raw.strip()
    # Strip ```json ... ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$",          "", text)
    try:
        data = json.loads(text)
        # Normalise: Gemini sometimes returns flat dict instead of sub_problems list
        if "sub_problems" not in data:
            data = {"sub_problems": [{
                "id":            "p1",
                "domain":        data.get("domain", fallback_domain),
                "problem_type":  data.get("problem_type", "general"),
                "input_summary": data.get("input_summary", ""),
                "parameters":    data.get("parameters", {}),
                "confidence":    data.get("confidence", 0.80),
            }]}
        return data
    except json.JSONDecodeError as exc:
        logger.error(f"Gemini returned invalid JSON: {exc}\nRaw: {raw[:300]}")
        raise RuntimeError(f"Parameter extractor returned invalid JSON: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Student-friendly Gemini explainer
# ─────────────────────────────────────────────────────────────────────────────

async def _explain_for_student(
    input_summary: str,
    raw_answer:    str,
) -> str:
    """
    Ask Gemini to rewrite the solver's raw markdown answer in plain,
    encouraging language.  Falls back to the raw answer on any failure.
    """
    prompt = _EXPLAIN_PROMPT.format(
        input_summary=input_summary,
        raw_answer=raw_answer,
    )
    try:
        explained = await _gemini_call(
            system_prompt=prompt,
            user_message="Rewrite the solution in a friendly, student-oriented style now.",
            temperature=0.3,   # slightly warmer for natural language
        )
        return explained.strip()
    except Exception as exc:
        logger.warning(f"Explainer failed, using raw answer: {exc}")
        return raw_answer   # graceful degradation


# ─────────────────────────────────────────────────────────────────────────────
# Solver dispatcher
# ─────────────────────────────────────────────────────────────────────────────

_SOLVER_MAP: dict[str, tuple[str, str]] = {
    "algebra":    ("solvers.algebra",       "solve_algebra"),
    "calculus":   ("solvers.calculus",       "solve_calculus"),
    "mechanics":  ("solvers.mechanics",      "solve_mechanics"),
    "structural": ("solvers.structural",     "solve_structural"),
    "fluids":     ("solvers.fluids",         "solve_fluids"),
    "thermo":     ("solvers.thermodynamics", "solve_thermo"),
    "circuits":   ("solvers.circuits",       "solve_circuits"),
    "physics":    ("solvers.physics",        "solve_physics"),
    "controls":   ("solvers.controls",       "solve_controls"),
    "statistics": ("solvers.statistics",     "solve_statistics"),
    "data_viz":   ("solvers.data_viz",       "solve_data_viz"),
}

# problem_type → effective domain (overrides the domain label when more specific)
_PT_DOMAIN_OVERRIDE: dict[str, str] = {
    "projectile_motion":     "mechanics",
    "kinematics":            "mechanics",
    "beam_deflection":       "structural",
    "cantilever_beam":       "structural",
    "simply_supported_beam": "structural",
    "truss_analysis":        "structural",
    "bernoulli_equation":    "fluids",
    "hydrostatics":          "fluids",
    "buoyancy":              "fluids",
    "snells_law":            "physics",
    "doppler_effect":        "physics",
    "wave_mechanics":        "physics",
    "bode_plot":             "controls",
    "step_response":         "controls",
    "linear_regression":     "statistics",
    "hypothesis_test":       "statistics",
}


def _get_solver(domain: str, problem_type: str):
    effective = _PT_DOMAIN_OVERRIDE.get(problem_type, domain).lower()
    entry = _SOLVER_MAP.get(effective) or _SOLVER_MAP.get(domain.lower())
    if entry is None:
        logger.error(f"No solver for domain='{domain}' type='{problem_type}'")
        return None
    module_path, fn_name = entry
    try:
        return getattr(importlib.import_module(module_path), fn_name)
    except (ImportError, AttributeError) as exc:
        logger.error(f"Cannot load {module_path}.{fn_name}: {exc}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Step filter  (drop hardcoded boilerplate before it reaches the client)
# ─────────────────────────────────────────────────────────────────────────────

_BOILERPLATE = [
    re.compile(r"^initializ(ing|ation)", re.I),
    re.compile(r"^(applying|computing|analyzing|evaluating|executing|running)"
               r"\s+(the\s+)?(kernel|engine|solver|system|module)", re.I),
    re.compile(r"(kernel|engine|solver)\s*\.{2,3}$", re.I),
]

def _is_real_step(content: str) -> bool:
    c = (content or "").strip()
    if len(c) < 15:
        return False
    if any(p.search(c) for p in _BOILERPLATE):
        return False
    # Must contain a number, math symbol, or LaTeX to be considered real output
    return bool(re.search(r"[\d$=+\-*/^\\()\[\]]", c))


# ─────────────────────────────────────────────────────────────────────────────
# Sub-problem pre-processing
# ─────────────────────────────────────────────────────────────────────────────

def _clean(domain: str, sub: dict) -> dict:
    """Strip English prose from expression field for non-symbolic domains."""
    sub  = dict(sub)
    params = dict(sub.get("parameters") or {})
    expr   = params.get("expression", "")
    if isinstance(expr, str):
        word_count   = len(re.findall(r"[A-Za-z]{3,}", expr))
        has_sentence = any(t in expr.lower() for t in
                           ("what", "find", "minimum", "maximum", "problem",
                            "value of", "how much", "determine"))
        if domain not in {"algebra", "calculus", "data_viz"} and (
            word_count > 6 or has_sentence
        ):
            params.pop("expression", None)
    sub["parameters"] = params
    return sub


# ─────────────────────────────────────────────────────────────────────────────
# Friendly error messages
# ─────────────────────────────────────────────────────────────────────────────

_FRIENDLY_ERRORS: dict[str, str] = {
    "mass":         "It looks like the mass wasn't specified. Try adding e.g. 'm = 5 kg'.",
    "velocity":     "The velocity doesn't seem to be given. Try adding e.g. 'v = 10 m/s'.",
    "length":       "The length or span wasn't found. Try adding e.g. 'L = 3 m'.",
    "force":        "No force value was detected. Try adding e.g. 'F = 50 N'.",
    "expression":   "No mathematical expression was found. Please type the equation or function.",
    "angle":        "The angle is missing. Try adding e.g. 'at 30°' or 'theta = 45'.",
}

def _friendly_missing(missing: list[str]) -> str:
    hints = [_FRIENDLY_ERRORS.get(p.lower(), f"'{p}' is needed but wasn't found.")
             for p in missing]
    if len(hints) == 1:
        return f"One thing missing: {hints[0]}"
    return (
        "A few things are needed to solve this:\n"
        + "\n".join(f"  • {h}" for h in hints)
        + "\n\nJust add them to your message and try again!"
    )


# ─────────────────────────────────────────────────────────────────────────────
# HTTP endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "engineering-studio"}


@app.options("/api/compute/solve")
async def options_solve():
    return {}


@app.post("/api/compute/solve")
async def solve(request: Request):
    logger.info("Solve request received")

    try:
        raw_data = await request.json()
    except Exception as exc:
        async def _bad():
            yield _err("Couldn't read the request — is it valid JSON?")
        return _sse(_bad())

    user_input = raw_data.get("input", "").strip()
    input_type = raw_data.get("type", "text")
    history    = raw_data.get("history", [])
    is_image   = input_type == "image"

    if not user_input and not is_image:
        async def _empty():
            yield _err("Nothing was sent! Type a question or upload an image.")
        return _sse(_empty())

    async def event_stream() -> AsyncGenerator[str, None]:
        acquired = False
        try:
            # ── Concurrency gate ──────────────────────────────────────────────
            try:
                await asyncio.wait_for(solve_semaphore.acquire(), timeout=3.0)
                acquired = True
            except asyncio.TimeoutError:
                yield _err(
                    "The server is handling several requests right now — "
                    "please wait a moment and try again."
                )
                return

            # ── Routing ───────────────────────────────────────────────────────
            if input_type == "data":
                routing = {"sub_problems": [{
                    "id":            "p1",
                    "domain":        "data_viz",
                    "problem_type":  "table_plot",
                    "input_summary": raw_data.get("filename", "Uploaded dataset"),
                    "parameters":    {"table_data": user_input},
                    "confidence":    1.0,
                }]}
            else:
                try:
                    routing = await route_and_extract(user_input, is_image, history)
                except Exception as exc:
                    yield _err(
                        f"Hmm, I had trouble understanding the input: {exc}\n"
                        "Try rephrasing and make sure you've included numbers and units."
                    )
                    return

            if "error" in routing:
                yield _err(
                    "Routing failed: " + routing["error"] + "\n"
                    "Please try again or rephrase your question."
                )
                return

            sub_problems = routing.get("sub_problems") or []
            if not sub_problems:
                yield _err(
                    "I couldn't figure out what type of problem this is. "
                    "Try including keywords like 'projectile', 'beam', 'circuit', etc."
                )
                return

            # ── Solve each sub-problem ────────────────────────────────────────
            for idx, sub in enumerate(sub_problems):
                domain       = sub.get("domain",       "unknown").lower()
                problem_type = sub.get("problem_type", "general").lower()
                problem_id   = sub.get("id",           f"p{idx + 1}")
                input_summary = sub.get("input_summary", user_input)

                sub = _clean(domain, sub)
                sub.setdefault("parameters", {})

                # Merge supplemental params from client
                supplemental = {
                    k: parse_user_supplied_value(v)
                    for k, v in raw_data.get("supplemental_params", {}).items()
                }
                sub["parameters"] = resolve_numeric_expressions(
                    apply_standard_defaults(merge_params(sub["parameters"], supplemental))
                )
                if raw_data.get("plot_config"):
                    sub["parameters"]["plot_config"] = raw_data["plot_config"]

                sub["raw_query"]        = input_summary
                sub["topic"]            = domain
                sub["requested_method"] = (
                    sub["parameters"].get("method") or raw_data.get("method")
                )

                # ── Missing parameter check ───────────────────────────────────
                missing = find_missing_params(
                    domain, problem_type, sub["parameters"], sub["raw_query"]
                )
                if missing:
                    yield _evt({
                        "type":                "needs_parameters",
                        "problem_id":          problem_id,
                        "message":             _friendly_missing(missing),
                        "missing_params":      missing,
                        "problem_description": input_summary,
                    })
                    return

                # ── Get solver ────────────────────────────────────────────────
                solver_fn = _get_solver(domain, problem_type)
                if not solver_fn:
                    yield _evt({
                        "type":       "final",
                        "answer":     (
                            f"No solver is available yet for **{domain}** / "
                            f"**{problem_type}**.\n\n"
                            "This feature may be coming soon — try a different "
                            "problem type for now."
                        ),
                        "problem_id": problem_id,
                    })
                    continue

                # ── Stream solver output ──────────────────────────────────────
                raw_answer_parts: list[str] = []

                try:
                    async with asyncio.timeout(SOLVE_TIMEOUT_SECONDS):
                        async for chunk in solver_fn(sub):
                            chunk["problem_id"] = problem_id

                            # Drop boilerplate steps
                            if chunk.get("type") == "step":
                                if not _is_real_step(chunk.get("content", "")):
                                    continue

                            # Collect raw answer for the explainer
                            if chunk.get("type") == "final":
                                raw_answer_parts.append(chunk.get("answer", ""))

                            # Multi-problem prefix
                            if len(sub_problems) > 1 and chunk.get("type") == "final":
                                chunk["answer"] = (
                                    f"### Part {idx + 1}: {input_summary}\n\n"
                                    + chunk.get("answer", "")
                                )

                            # Polish
                            if chunk.get("type") == "final":
                                chunk["answer"] = polish_final_answer(
                                    chunk.get("answer", ""),
                                    domain=domain,
                                    problem_type=problem_type,
                                )

                            # MCQ matching
                            if chunk.get("type") == "final" and sub.get("options"):
                                ans = str(chunk.get("answer", ""))
                                matched = False
                                for opt in sub["options"]:
                                    if (str(opt.get("label","")).lower() in ans.lower()
                                            or str(opt.get("val","")) in ans):
                                        chunk["answer"] = ans + f"\n\n**Answer: {opt['label']}**"
                                        matched = True
                                        break
                                if not matched:
                                    chunk["answer"] = ans + "\n\n*(None of the provided options matched the computed result.)*"

                            yield _evt(chunk)

                except asyncio.TimeoutError:
                    yield _err(
                        f"The **{domain}** solver took too long on this one. "
                        "Try simplifying the problem or breaking it into smaller parts.",
                        problem_id,
                    )
                    continue
                except Exception as exc:
                    logger.error(f"Solver error [{domain}]: {exc}", exc_info=True)
                    yield _err(
                        f"Something went wrong inside the **{domain}** solver: {exc}\n"
                        "Double-check your values and try again.",
                        problem_id,
                    )
                    continue

                # ── Gemini explanation (runs AFTER solver finishes) ──────────
                if raw_answer_parts:
                    raw_combined = "\n\n".join(raw_answer_parts)
                    explained = await _explain_for_student(input_summary, raw_combined)
                    yield _evt({
                        "type":       "explanation",
                        "answer":     explained,
                        "problem_id": problem_id,
                    })

        except Exception as exc:
            logger.error(f"Unexpected error in event_stream: {exc}", exc_info=True)
            yield _err(f"An unexpected error occurred: {exc}")
        finally:
            if acquired:
                solve_semaphore.release()

    return _sse(event_stream())


# ─────────────────────────────────────────────────────────────────────────────
# Static frontend
# ─────────────────────────────────────────────────────────────────────────────

_here         = os.path.dirname(os.path.abspath(__file__))
_frontend_dir = os.path.abspath(os.path.join(_here, "..", "frontend", "dist"))
if os.path.exists(_frontend_dir):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="static")


# ─────────────────────────────────────────────────────────────────────────────
# Dev server
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
