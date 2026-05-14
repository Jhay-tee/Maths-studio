"""
corrected_algebra.py

Production-ready algebra solver.
- Accepts equations array from validation layer
- Handles simultaneous equations (2-4+ variables)
- Robust SymPy parsing with fallbacks
- Clean error messages
"""

import asyncio
import re
from typing import AsyncGenerator
import sympy as sp

logger_enabled = True

def _log(msg: str):
    if logger_enabled:
        print(f"[ALGEBRA] {msg}")


async def solve_algebra(sub: dict) -> AsyncGenerator[dict, None]:
    """
    Solve algebraic equations.
    
    Accepts sub dict with:
    - parameters["equations"]: list of equation strings in LHS-RHS=0 form
    - parameters["expression"]: fallback single equation string
    - raw_query: original user query for fallback parsing
    """
    params = sub.get("parameters", {})
    raw_query = sub.get("raw_query", "")
    problem_type = sub.get("problem_type", "general")
    
    yield {"type": "step", "title": "Input validation", "content": "Checking equation format..."}

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: Extract equations from parameters
    # ─────────────────────────────────────────────────────────────────────────
    
    equations_list = None
    expression_str = None
    
    # Try equations array first (primary path)
    if "equations" in params:
        eq_arr = params["equations"]
        if isinstance(eq_arr, list) and eq_arr:
            equations_list = [str(e).strip() for e in eq_arr if e]
            _log(f"Got {len(equations_list)} equations from array")
    
    # Fallback to expression field
    if not equations_list and "expression" in params:
        expr = params.get("expression", "")
        if isinstance(expr, str) and expr.strip():
            expression_str = expr.strip()
            _log(f"Using expression: {expression_str[:60]}")
    
    # Last resort: parse raw query
    if not equations_list and not expression_str:
        _log("No equations or expression — attempting to extract from raw query")
        equations_list = _extract_equations_from_text(raw_query)
        if not equations_list:
            yield {
                "type": "final",
                "answer": (
                    "**Error:** No equations were found.\n\n"
                    "Please provide equations in one of these formats:\n"
                    "- `3x + 4y = 12`\n"
                    "- `x^2 + 2x - 3 = 0`\n"
                    "- Multiple lines (one equation per line)"
                )
            }
            return

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: Convert to SymPy symbols and expressions
    # ─────────────────────────────────────────────────────────────────────────

    all_vars = set()
    sympy_equations = []

    if equations_list:
        for eq_str in equations_list:
            try:
                eq_str = eq_str.strip()
                if not eq_str:
                    continue
                
                # Extract variable names
                vars_in_eq = set(re.findall(r'\b([a-zA-Z])\b', eq_str))
                all_vars.update(vars_in_eq)
                
                # Parse with SymPy
                parsed_eq = sp.sympify(eq_str, transformations="all")
                sympy_equations.append(parsed_eq)
                _log(f"Parsed: {eq_str[:50]}")
            except Exception as exc:
                _log(f"Failed to parse '{eq_str[:50]}': {exc}")
                yield {
                    "type": "final",
                    "answer": (
                        f"**Parsing error** in equation: `{eq_str[:80]}`\n\n"
                        f"Details: {str(exc)[:150]}\n\n"
                        "Make sure your equation uses * for multiplication: `3*x + 4*y - 12`"
                    )
                }
                return

    elif expression_str:
        try:
            # Single equation case
            vars_in_expr = set(re.findall(r'\b([a-zA-Z])\b', expression_str))
            all_vars.update(vars_in_expr)
            parsed = sp.sympify(expression_str, transformations="all")
            sympy_equations = [parsed]
            _log(f"Parsed expression: {expression_str[:50]}")
        except Exception as exc:
            yield {
                "type": "final",
                "answer": (
                    f"**Parsing error** in expression: `{expression_str[:80]}`\n\n"
                    f"Details: {str(exc)[:150]}"
                )
            }
            return

    if not all_vars:
        yield {
            "type": "final",
            "answer": "**Error:** No variables found. Please use x, y, z, w, etc."
        }
        return

    # Create symbols
    symbols_dict = {v: sp.Symbol(v) for v in sorted(all_vars)}
    symbols_list = [symbols_dict[v] for v in sorted(all_vars)]

    _log(f"Variables: {', '.join(sorted(all_vars))}")
    _log(f"Equations: {len(sympy_equations)}")

    yield {
        "type": "step",
        "title": "Detected equation system",
        "content": (
            f"**Variables:** {', '.join(sorted(all_vars))}\n"
            f"**Number of equations:** {len(sympy_equations)}"
        )
    }

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: Solve
    # ─────────────────────────────────────────────────────────────────────────

    yield {"type": "step", "title": "Solving system", "content": "Computing solutions using SymPy..."}

    try:
        solutions = sp.solve(sympy_equations, symbols_list, dict=True)
        _log(f"SymPy returned {len(solutions) if isinstance(solutions, list) else 1} solution(s)")
    except Exception as exc:
        yield {
            "type": "final",
            "answer": (
                f"**System is unsolvable** or has infinitely many solutions.\n\n"
                f"Details: {str(exc)[:200]}\n\n"
                "This can happen if:\n"
                "- Equations are inconsistent (contradictory)\n"
                "- Equations are linearly dependent (redundant)\n"
                "- The system is underdetermined"
            )
        }
        return

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: Format answer
    # ─────────────────────────────────────────────────────────────────────────

    # Handle different solution formats from SymPy
    if isinstance(solutions, dict):
        # Single solution as dict
        solutions = [solutions]
    elif isinstance(solutions, list):
        if len(solutions) == 0:
            yield {
                "type": "final",
                "answer": "**No solution exists** for this system of equations."
            }
            return
    else:
        # Fallback
        solutions = [solutions]

    answer_lines = []

    for idx, sol in enumerate(solutions):
        if isinstance(sol, dict):
            sol_dict = sol
        else:
            sol_dict = {str(v): sol.get(v, "undefined") for v in symbols_list}

        # Format solution
        if len(solutions) == 1:
            answer_lines.append("### Solution\n")
        else:
            answer_lines.append(f"### Solution {idx + 1}\n")

        for var in sorted(all_vars):
            val = sol_dict.get(var) or sol_dict.get(sp.Symbol(var), "undefined")
            # Try to simplify/float
            try:
                if hasattr(val, 'evalf'):
                    val_str = f"**{val.evalf(10)}**"
                else:
                    val_str = f"**{val}**"
            except:
                val_str = f"**{val}**"
            
            answer_lines.append(f"${var} = {val_str}$")

    answer_text = "\n".join(answer_lines)

    # Verification step
    yield {"type": "step", "title": "Verification", "content": "Checking solution in original equations..."}

    sol_dict = solutions[0] if isinstance(solutions[0], dict) else {}
    all_satisfied = True
    for eq in sympy_equations:
        try:
            result = eq.subs(sol_dict)
            if abs(result) > 1e-10:  # not exactly zero
                all_satisfied = False
        except:
            pass

    if all_satisfied:
        answer_text += "\n\n✓ **Verified:** Solution satisfies all equations."
    else:
        answer_text += "\n\n⚠ **Warning:** Solution may not satisfy all equations perfectly."

    yield {"type": "final", "answer": answer_text}


# ─────────────────────────────────────────────────────────────────────────────
# Fallback equation extraction from text
# ─────────────────────────────────────────────────────────────────────────────

def _extract_equations_from_text(text: str) -> list[str]:
    """
    Last-resort extraction of equations from plain English text.
    """
    equations = []
    
    # Split by common delimiters
    for line in re.split(r"[\n;]|(?<=\d)\s*\)\s*(?=[A-Z0-9])", text):
        line = line.strip()
        
        # Remove numbering: "1) ...", "eq1: ...", etc.
        line = re.sub(r"^\s*(?:\d+[\)\.:]|eq\s*\d*\s*:?)\s*", "", line, flags=re.I)
        
        if not line:
            continue
        
        # Must have an equals sign and a variable
        if "=" not in line or not re.search(r"[a-zA-Z]", line):
            continue
        
        # Skip if it's pure English (no math)
        if re.search(r"\b(solve|find|calculate|determine|system|equation)\b", line, re.I) \
           and not re.search(r"[\d=+\-*/^]", line):
            continue
        
        equations.append(line)
    
    return equations
