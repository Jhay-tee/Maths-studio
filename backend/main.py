"""
main.py  —  Engineering Computation Studio
FastAPI backend with two-layer routing and student-friendly responses.

Routing pipeline
────────────────
1. Layer 1  router.fast_classify()     deterministic, zero I/O, O(n_tokens)
   └─ L1 now also runs domain-specific pre-extractors (algebra equations,
      structural params) and stores them in ClassificationResult.pre_extracted_params
2. Layer 2  Gemini parameter extractor called with domain already locked
   └─ L1 uncertain → Gemini does classification + extraction together

Validation firewall  (NEW in v2)
─────────────────────────────────
After Gemini extraction, validate_and_normalize() runs before ANY solver call.
It repairs malformed JSON, strips English prose from expressions, extracts
equation arrays from algebra input, prevents over-splitting of engineering
problems, and merges L1 pre-extracted params (which always win on conflict).

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

        cl = request.headers.get("content-length")
        if cl:
            try:
                if int(cl) > MAX_REQUEST_BYTES:
                    return JSONResponse({"error": "Request payload too large."}, status_code=413)
            except ValueError:
                pass

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

════════════════════════════════════════════════════════
CRITICAL ALGEBRA/CALCULUS RULES  (READ CAREFULLY)
════════════════════════════════════════════════════════
For simultaneous equations or any equation system:
  ✗ WRONG:  "expression": "Solve the system of three linear equations..."
  ✓ RIGHT:  "equations": ["3*x + 4*y - 2*z - 12", "2*x - y + 5*z - 9", "x + 3*y + z - 8"]

Rules for the "equations" array:
  • Each entry is LHS − RHS form (move everything to the left side).
  • Use explicit multiplication: 3x → 3*x, 4y → 4*y, 2z → 2*z.
  • NO English words inside any equation string.
  • For a single equation, still use "equations": ["..."] not "expression".

The "expression" field MUST contain ONLY pure math/SymPy syntax.
  • No English words whatsoever.
  • If the input is a word problem, DO NOT put the problem sentence in "expression".
  • Strip all English verbs: "Solve", "Find", "Calculate", "the equation", etc.
  • If you cannot produce pure math, OMIT the expression field entirely.
════════════════════════════════════════════════════════

GENERAL EXTRACTION RULES:
- Normalise ALL values to SI units:
    kN → ×1000  |  cm → ÷100  |  mm → ÷1000  |  GPa → ×1e9
    kPa → ×1e3  |  minutes → ×60  |  hours → ×3600
- For tolerances: nominal → key as-is; absolute sigma → key + "_sigma"
- Split multi-part questions into separate items in sub_problems ONLY if
  they are genuinely different domains. Engineering problems asking for
  reactions + shear + bending moment are ONE sub_problem, not three.
- DO NOT SOLVE the problem. DO NOT provide numerical answers.

OUTPUT (return ONLY this JSON, nothing else):
{{
  "sub_problems": [
    {{
      "id": "p1",
      "problem_type": "<specific type e.g. simultaneous_equations>",
      "input_summary": "<clean one-line restatement of the problem>",
      "parameters": {{
        "equations": ["<eq1 in LHS-RHS=0 form>", ...],
        "<param_key>": <numeric_value>,
        ...
      }},
      "confidence": 0.97
    }}
  ]
}}
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

════════════════════════════════════════════════════════
CRITICAL ALGEBRA/CALCULUS RULES
════════════════════════════════════════════════════════
For equation systems, use an "equations" array, NOT "expression":
  • Each entry: LHS − RHS (everything on left side)
  • Explicit multiplication: 3x → 3*x
  • Zero English words inside equation strings
  • "expression" field = pure SymPy math only, or omit it

ANTI-SPLITTING RULE: Multi-ask engineering questions (reactions + shear +
bending moment, or find P + Q + R) are ONE sub_problem, not several.
════════════════════════════════════════════════════════

Same extraction rules:
- Normalise to SI.
- expression = pure math only, or omit.
- Do NOT solve.

OUTPUT (return ONLY this JSON):
{{
  "sub_problems": [
    {{
      "id": "p1",
      "domain": "<one of the listed domains>",
      "problem_type": "<specific type>",
      "input_summary": "<clean one-line restatement>",
      "parameters": {{
        "equations": ["<optional, for algebra/calculus systems>"],
        "<key>": <value>
      }},
      "confidence": 0.97
    }}
  ]
}}
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
# Validation + normalisation firewall  (NEW — runs after every Gemini call)
# ─────────────────────────────────────────────────────────────────────────────

# Patterns that indicate a value is English prose, not math
_PROSE_MARKERS = re.compile(
    r"\b(solve|find|calculate|determine|what\s+is|the\s+equation|"
    r"three|four|five|variables|given\s+that|such\s+that|where|"
    r"linear|system|simultaneous|unknown)\b",
    re.IGNORECASE,
)
_MATH_PRESENT  = re.compile(r"[\d=+\-*/^\\()\[\]]")
_IMPLICIT_MUL  = re.compile(r"(\d)([A-Za-z])")

# Engineering domains where multi-ask questions should NOT be split
_MERGE_DOMAINS = {"structural", "mechanics", "fluids", "thermo", "circuits"}


def _normalize_eq(eq: str) -> str:
    """Move RHS to left side and insert explicit multiplication."""
    eq = eq.strip()
    if "=" in eq:
        lhs, rhs = eq.split("=", 1)
        rhs = rhs.strip()
        lhs = lhs.strip()
        eq = f"({lhs}) - ({rhs})" if not rhs.startswith("-") else f"({lhs}) + ({rhs})"
    return _IMPLICIT_MUL.sub(r"\1*\2", eq).strip()


def _extract_equations_from_text(text: str) -> list[str]:
    """
    Last-resort equation extraction directly from free text.
    Finds lines that look like math equations and normalises them.
    """
    equations = []
    for line in re.split(r"[\n;]|(?<=\d)\s*\)\s*(?=[0-9A-Za-z\-])", text):
        line = line.strip()
        # Strip leading numbering like "1)" or "eq2:"
        line = re.sub(r"^\s*(?:\d+[\)\.:]|eq\s*\d*\s*:?)\s*", "", line, flags=re.I)
        if not line:
            continue
        if "=" not in line:
            continue
        if not re.search(r"[A-Za-z]", line):
            continue  # no variables
        if _PROSE_MARKERS.search(line) and not re.search(r"\d", line):
            continue  # pure English with no numbers
        equations.append(_normalize_eq(line))
    return equations


def _sanitize_params(params: dict, domain: str, raw_query: str) -> dict:
    """
    Clean a single sub-problem's parameters dict.
    • Removes English prose from "expression"
    • Extracts "equations" array for algebra/calculus if missing
    • Inserts explicit multiplication in any equation strings
    • Flattens accidentally nested {"parameters": {...}} structures
    • Removes null/empty values
    """
    # Flatten nested params (Gemini occasionally wraps params in a "parameters" key)
    if "parameters" in params and isinstance(params["parameters"], dict):
        inner = params.pop("parameters")
        params.update(inner)

    # ── expression field sanitation ──────────────────────────────────────────
    expr = params.get("expression", "")
    if isinstance(expr, str) and expr.strip():
        # Case 1: pure English sentence — delete it
        if _PROSE_MARKERS.search(expr) and not _MATH_PRESENT.search(expr):
            logger.warning(f"Dropping English expression: '{expr[:80]}'")
            del params["expression"]

        # Case 2: starts with English verb prefix — strip the prefix
        elif _PROSE_MARKERS.search(expr) and _MATH_PRESENT.search(expr):
            cleaned = re.sub(
                r"^(solve|find|calculate|evaluate|compute|simplify|determine)"
                r"\s*[:\-]?\s*",
                "", expr, flags=re.I,
            ).strip()
            if cleaned and _MATH_PRESENT.search(cleaned):
                params["expression"] = _IMPLICIT_MUL.sub(r"\1*\2", cleaned)
            else:
                del params["expression"]

        # Case 3: looks like math — just ensure explicit multiplication
        else:
            params["expression"] = _IMPLICIT_MUL.sub(r"\1*\2", expr)

    # ── equations array sanitation ───────────────────────────────────────────
    if "equations" in params:
        raw_eqs = params["equations"]
        if isinstance(raw_eqs, str):
            # Gemini sometimes returns a single string instead of a list
            raw_eqs = [raw_eqs]
        cleaned_eqs = []
        for eq in raw_eqs:
            if not isinstance(eq, str):
                continue
            eq = eq.strip()
            # Drop entries that are English sentences (no math operators)
            if _PROSE_MARKERS.search(eq) and not _MATH_PRESENT.search(eq):
                continue
            cleaned_eqs.append(_normalize_eq(eq) if "=" in eq else
                                _IMPLICIT_MUL.sub(r"\1*\2", eq))
        if cleaned_eqs:
            params["equations"] = cleaned_eqs
        else:
            del params["equations"]

    # ── For algebra/calculus: if no equations AND no clean expression,
    #    try extracting from the raw query text ─────────────────────────────
    if domain in ("algebra", "calculus"):
        has_expr = bool(params.get("expression", "").strip())
        has_eqs  = bool(params.get("equations"))
        if not has_expr and not has_eqs and raw_query:
            recovered = _extract_equations_from_text(raw_query)
            if recovered:
                logger.info(f"Recovered {len(recovered)} equation(s) from raw query text")
                params["equations"] = recovered

    # ── Remove null/empty entries ────────────────────────────────────────────
    params = {k: v for k, v in params.items()
              if v is not None and v != "" and v != [] and v != {}}

    return params


def _prevent_over_splitting(sub_problems: list) -> list:
    """
    If all sub-problems share the same engineering domain, merge them
    into one. This prevents Gemini from exploding a single beam question
    into three separate sub-problems.
    """
    if len(sub_problems) <= 1:
        return sub_problems

    domains = {sp.get("domain", "").lower() for sp in sub_problems}
    if len(domains) == 1 and domains.issubset(_MERGE_DOMAINS):
        merged = dict(sub_problems[0])
        merged["input_summary"] = " | ".join(
            sp.get("input_summary", "") for sp in sub_problems
            if sp.get("input_summary")
        )
        merged_params: dict = {}
        for sp in reversed(sub_problems):   # first sub wins on key conflict
            merged_params.update(sp.get("parameters") or {})
        merged["parameters"] = merged_params
        logger.info(
            f"Merged {len(sub_problems)} sub-problems into one "
            f"(domain={list(domains)[0]})"
        )
        return [merged]

    return sub_problems


def validate_and_normalize(routing: dict, raw_query: str = "") -> dict:
    """
    Firewall between Gemini extraction and solver execution.

    Accepts the routing dict returned by route_and_extract() and returns
    a cleaned version where every sub-problem's parameters are safe to
    pass directly to a solver.

    raw_query is the original user text, used as a fallback for equation
    extraction when Gemini put English into the expression field.
    """
    subs = routing.get("sub_problems") or []

    # Sanitize each sub-problem's parameters
    cleaned_subs = []
    for sp in subs:
        if not isinstance(sp, dict):
            continue
        sp = dict(sp)
        domain = sp.get("domain", "unknown").lower()
        params = dict(sp.get("parameters") or {})
        sp["parameters"] = _sanitize_params(params, domain, raw_query)
        cleaned_subs.append(sp)

    # Merge over-split engineering problems
    cleaned_subs = _prevent_over_splitting(cleaned_subs)

    routing["sub_problems"] = cleaned_subs
    return routing


# ─────────────────────────────────────────────────────────────────────────────
# Routing orchestrator
# ─────────────────────────────────────────────────────────────────────────────

async def route_and_extract(
    user_input:      str,
    is_image:        bool,
    history:         list,
    l1_result:       ClassificationResult | None = None,
) -> dict:
    """
    Returns a standard routing dict:
    {
        "sub_problems": [ { "id", "domain", "problem_type",
                            "input_summary", "parameters", "confidence" } ]
    }

    l1_result is passed in from the caller so we can merge pre_extracted_params
    without running fast_classify() twice.
    """
    if is_image:
        raw = await _gemini_call(
            system_prompt=_CLASSIFY_AND_EXTRACT_PROMPT,
            user_message="Classify and extract parameters from this image. Return only JSON.",
            history=history,
            image_b64=user_input,
        )
        return _parse_gemini_json(raw, fallback_domain="unknown")

    if l1_result is not None:
        logger.info(
            f"L1 → domain={l1_result.domain}  type={l1_result.problem_type}  "
            f"conf={l1_result.confidence}  signals={l1_result.matched_signals}"
        )
        prompt = _EXTRACT_PROMPT.format(domain=l1_result.domain)
        try:
            raw = await _gemini_call(
                system_prompt=prompt,
                user_message=f"Extract parameters.\n\nInput: {user_input}",
                history=history,
            )
            routing = _parse_gemini_json(raw, fallback_domain=l1_result.domain)

            # L1 domain is authoritative
            for sp in routing.get("sub_problems", []):
                sp["domain"] = l1_result.domain
                if sp.get("confidence", 0) < l1_result.confidence:
                    sp["confidence"] = l1_result.confidence

                # ── Merge L1 pre-extracted params (L1 wins on conflict) ──────
                if l1_result.pre_extracted_params:
                    gemini_params = sp.get("parameters") or {}
                    # L1 params take priority: update gemini dict first,
                    # then overlay L1 on top
                    merged = {**gemini_params, **l1_result.pre_extracted_params}
                    sp["parameters"] = merged
                    logger.info(
                        f"Merged L1 pre-extracted params into sub-problem: "
                        f"{list(l1_result.pre_extracted_params.keys())}"
                    )

            return routing

        except Exception as exc:
            logger.warning(f"Gemini extraction failed after L1: {exc}. Using L1 skeleton.")
            # Fall back to a skeleton built entirely from L1 data
            return {
                "sub_problems": [{
                    "id":            "p1",
                    "domain":        l1_result.domain,
                    "problem_type":  l1_result.problem_type,
                    "input_summary": user_input,
                    "parameters":    l1_result.pre_extracted_params or {},
                    "confidence":    l1_result.confidence,
                }]
            }

    # L1 uncertain — Gemini classifies + extracts
    logger.info("L1 uncertain — escalating to Gemini full classification")
    try:
        raw = await _gemini_call(
            system_prompt=_CLASSIFY_AND_EXTRACT_PROMPT,
            user_message=(
                "Classify and extract parameters. Return only JSON.\n\n"
                f"Input: {user_input}"
            ),
            history=history,
        )
        return _parse_gemini_json(raw, fallback_domain="unknown")
    except Exception as exc:
        return {"error": str(exc)}


def _parse_gemini_json(raw: str, fallback_domain: str) -> dict:
    """
    Parse Gemini JSON response with four fallback strategies:
    1. Direct parse
    2. Extract first {...} block
    3. Truncate to last valid closing brace
    4. Graceful skeleton fallback (never crashes)
    """
    text = raw.strip()
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$",       "", text, flags=re.MULTILINE)
    text = text.strip()

    for attempt, candidate in enumerate([
        text,
        # Strategy 2: first {...} block
        (lambda m: m.group() if (m := re.search(r"\{.*\}", text, re.DOTALL)) else None)(),
        # Strategy 3: up to last "}"
        text[:text.rfind("}") + 1] if "}" in text else None,
    ]):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            return _normalize_routing_shape(data, fallback_domain)
        except json.JSONDecodeError:
            logger.debug(f"JSON parse strategy {attempt + 1} failed")

    logger.warning(f"All JSON strategies failed — using skeleton. Raw[:200]: {raw[:200]}")
    return {
        "sub_problems": [{
            "id":            "p1",
            "domain":        fallback_domain,
            "problem_type":  "general",
            "input_summary": "",
            "parameters":    {},
            "confidence":    0.50,
        }]
    }


def _normalize_routing_shape(data: dict, fallback_domain: str) -> dict:
    """Ensure output always has the sub_problems list structure."""
    if "sub_problems" not in data:
        return {"sub_problems": [{
            "id":            "p1",
            "domain":        data.get("domain", fallback_domain),
            "problem_type":  data.get("problem_type", "general"),
            "input_summary": data.get("input_summary", ""),
            "parameters":    data.get("parameters", {}),
            "confidence":    data.get("confidence", 0.80),
        }]}

    subs = data["sub_problems"]
    if not isinstance(subs, list):
        subs = [subs] if isinstance(subs, dict) else []
    data["sub_problems"] = [s for s in subs if isinstance(s, dict) and s]
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Student-friendly Gemini explainer
# ─────────────────────────────────────────────────────────────────────────────

async def _explain_for_student(input_summary: str, raw_answer: str) -> str:
    prompt = _EXPLAIN_PROMPT.format(
        input_summary=input_summary,
        raw_answer=raw_answer,
    )
    try:
        explained = await _gemini_call(
            system_prompt=prompt,
            user_message="Rewrite the solution in a friendly, student-oriented style now.",
            temperature=0.3,
        )
        return explained.strip()
    except Exception as exc:
        logger.warning(f"Explainer failed, using raw answer: {exc}")
        return raw_answer


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
# Step filter
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
    return bool(re.search(r"[\d$=+\-*/^\\()\[\]]", c))


# ─────────────────────────────────────────────────────────────────────────────
# Sub-problem pre-processing
# ─────────────────────────────────────────────────────────────────────────────

def _clean(domain: str, sub: dict) -> dict:
    """
    Domain-aware parameter cleaning called AFTER validate_and_normalize().
    This is a lightweight second pass — the heavy lifting is done by the
    validation firewall above.

    Previously this skipped algebra/calculus (because they need expressions).
    Now it applies to ALL domains but is less aggressive for symbolic ones.
    """
    sub    = dict(sub)
    params = dict(sub.get("parameters") or {})
    expr   = params.get("expression", "")

    if isinstance(expr, str) and expr.strip():
        # Count English words (3+ chars) in the expression
        word_count   = len(re.findall(r"[A-Za-z]{3,}", expr))
        has_sentence = any(t in expr.lower() for t in (
            "what", "find", "minimum", "maximum", "problem",
            "value of", "how much", "determine",
        ))

        # For non-symbolic domains: be aggressive
        if domain not in {"algebra", "calculus", "data_viz"}:
            if word_count > 6 or has_sentence:
                params.pop("expression", None)

        # For symbolic domains: only remove if it's clearly all English
        else:
            if word_count > 10 and not _MATH_PRESENT.search(expr):
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
            try:
                await asyncio.wait_for(solve_semaphore.acquire(), timeout=3.0)
                acquired = True
            except asyncio.TimeoutError:
                yield _err(
                    "The server is handling several requests right now — "
                    "please wait a moment and try again."
                )
                return

            # ── Layer 1 classification (run once, pass result to route_and_extract) ──
            l1_result: ClassificationResult | None = None
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
                if not is_image:
                    try:
                        l1_result = fast_classify(user_input)
                    except Exception as exc:
                        logger.warning(f"L1 classifier error: {exc}")
                        l1_result = None

                try:
                    routing = await route_and_extract(
                        user_input, is_image, history, l1_result
                    )
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

            # ── VALIDATION FIREWALL ───────────────────────────────────────────
            # Runs on every request — cleans Gemini output before solver sees it
            routing = validate_and_normalize(routing, raw_query=user_input)
            # ─────────────────────────────────────────────────────────────────

            sub_problems = routing.get("sub_problems") or []
            if not sub_problems:
                yield _err(
                    "I couldn't figure out what type of problem this is. "
                    "Try including keywords like 'projectile', 'beam', 'circuit', etc."
                )
                return

            for idx, sub in enumerate(sub_problems):
                domain       = sub.get("domain",       "unknown").lower()
                problem_type = sub.get("problem_type", "general").lower()
                problem_id   = sub.get("id",           f"p{idx + 1}")
                input_summary = sub.get("input_summary", user_input)

                sub = _clean(domain, sub)
                sub.setdefault("parameters", {})

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

                raw_answer_parts: list[str] = []

                try:
                    async with asyncio.timeout(SOLVE_TIMEOUT_SECONDS):
                        async for chunk in solver_fn(sub):
                            chunk["problem_id"] = problem_id

                            if chunk.get("type") == "step":
                                if not _is_real_step(chunk.get("content", "")):
                                    continue

                            if chunk.get("type") == "final":
                                raw_answer_parts.append(chunk.get("answer", ""))

                            if len(sub_problems) > 1 and chunk.get("type") == "final":
                                chunk["answer"] = (
                                    f"### Part {idx + 1}: {input_summary}\n\n"
                                    + chunk.get("answer", "")
                                )

                            if chunk.get("type") == "final":
                                chunk["answer"] = polish_final_answer(
                                    chunk.get("answer", ""),
                                    domain=domain,
                                    problem_type=problem_type,
                                )

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
                                    chunk["answer"] = ans + "\n\n*(None of the provided options matched.)*"

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
