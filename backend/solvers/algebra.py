"""
corrected_algebra_v2.py

PRODUCTION-READY Algebra Solver (v2)
- Compatible with ALL SymPy versions (1.8+)
- No deprecated parameters (fixes sympify() error)
- Handles simultaneous equations (2+ variables)
- Quadratic, polynomial, single equations
- Robust error handling
- Clean SSE output format
"""

import asyncio
import re
from typing import AsyncGenerator
import sympy as sp
from sympy import symbols, solve, Eq, sympify, simplify

logger_enabled = True


def _log(msg: str):
    if logger_enabled:
        print(f"[ALGEBRA] {msg}")


async def solve_algebra(sub: dict) -> AsyncGenerator[dict, None]:
    """
    Solve algebraic equations.

    Accepts sub dict with:
    - parameters["equations"]: list of equation strings
    - parameters["expression"]: fallback single equation
    - raw_query: original user query for fallback parsing
    """
    params = sub.get("parameters", {})
    raw_query = sub.get("raw_query", "")

    yield {
        "type": "step",
        "title": "Input validation",
        "content": "Checking equation format..."
    }

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: Extract equations
    # ─────────────────────────────────────────────────────────────────────────

    equations_list = None
    expression_str = None

    if "equations" in params:
        eq_arr = params.get("equations", [])
        if isinstance(eq_arr, list) and eq_arr:
            equations_list = [str(e).strip() for e in eq_arr if e]
            _log(f"Got {len(equations_list)} equation(s)")

    if not equations_list and "expression" in params:
        expr = params.get("expression", "")
        if isinstance(expr, str) and expr.strip():
            expression_str = expr.strip()
            _log(f"Using expression: {expression_str[:60]}")

    if not equations_list and not expression_str:
        equations_list = _extract_equations_from_text(raw_query)
        if not equations_list:
            yield {
                "type": "final",
                "answer": (
                    "**Error:** No equations found.\n\n"
                    "Provide equations like:\n"
                    "- `2*x + 3*y = 12` and `x - y = 1`\n"
                    "- `x**2 - 5*x + 6 = 0`"
                )
            }
            return

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: Parse and collect variables
    # ─────────────────────────────────────────────────────────────────────────

    all_vars = set()
    sympy_equations = []

    if equations_list:
        for i, eq_str in enumerate(equations_list):
            try:
                eq_str = eq_str.strip()
                if not eq_str:
                    continue

                # Extract variables
                vars_in_eq = set(re.findall(r"\b([a-zA-Z])\b", eq_str))
                all_vars.update(vars_in_eq)

                # Parse equation WITHOUT transformations parameter
                if "=" in eq_str:
                    lhs_str, rhs_str = eq_str.split("=", 1)
                    lhs = sympify(lhs_str.strip())
                    rhs = sympify(rhs_str.strip())
                    eq = Eq(lhs, rhs)
                else:
                    # Assume = 0
                    expr = sympify(eq_str)
                    eq = Eq(expr, 0)

                sympy_equations.append(eq)
                _log(f"Parsed: {eq_str[:50]}")

            except Exception as exc:
                _log(f"Parse error in equation {i+1}: {exc}")
                yield {
                    "type": "final",
                    "answer": (
                        f"**Parsing error** in equation {i+1}:\n"
                        f"`{eq_str[:70]}`\n\n"
                        f"Error: {str(exc)[:100]}\n\n"
                        "**Tips:**\n"
                        "- Use `*` for multiply: `3*x` not `3x`\n"
                        "- Use `**` for power: `x**2` not `x^2`"
                    )
                }
                return

    elif expression_str:
        try:
            vars_in_expr = set(re.findall(r"\b([a-zA-Z])\b", expression_str))
            all_vars.update(vars_in_expr)

            if "=" in expression_str:
                lhs_str, rhs_str = expression_str.split("=", 1)
                lhs = sympify(lhs_str.strip())
                rhs = sympify(rhs_str.strip())
                eq = Eq(lhs, rhs)
            else:
                expr = sympify(expression_str)
                eq = Eq(expr, 0)

            sympy_equations = [eq]
            _log(f"Parsed expression: {expression_str[:50]}")

        except Exception as exc:
            yield {
                "type": "final",
                "answer": f"**Parse error:** {str(exc)[:150]}"
            }
            return

    if not all_vars:
        yield {
            "type": "final",
            "answer": "**Error:** No variables detected (x, y, z, etc.)"
        }
        return

    # Create symbols
    var_symbols = [sp.Symbol(v, real=True) for v in sorted(all_vars)]

    _log(f"Variables: {', '.join(v.name for v in var_symbols)}")
    _log(f"Equations: {len(sympy_equations)}")

    yield {
        "type": "step",
        "title": "System detected",
        "content": (
            f"**Variables:** {', '.join(v.name for v in var_symbols)}\n"
            f"**Equations:** {len(sympy_equations)}"
        )
    }

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: Solve
    # ─────────────────────────────────────────────────────────────────────────

    yield {
        "type": "step",
        "title": "Solving",
        "content": "Computing solution..."
    }

    try:
        solutions = solve(sympy_equations, var_symbols, dict=True)

        if not solutions:
            yield {
                "type": "final",
                "answer": (
                    "**No solution found.**\n\n"
                    "The system may be:\n"
                    "- Inconsistent (contradictory)\n"
                    "- Dependent (redundant equations)\n"
                    "- Underdetermined"
                )
            }
            return

        _log(f"Found {len(solutions)} solution(s)")

    except Exception as exc:
        yield {
            "type": "final",
            "answer": (
                f"**Cannot solve this system.**\n\n"
                f"Error: {str(exc)[:150]}"
            )
        }
        return

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: Format answer
    # ─────────────────────────────────────────────────────────────────────────

    answer_lines = []

    for sol_idx, sol_dict in enumerate(solutions):
        if len(solutions) > 1:
            answer_lines.append(f"### Solution {sol_idx + 1}\n")
        else:
            answer_lines.append("### Solution\n")

        for sym in var_symbols:
            try:
                val = sol_dict.get(sym)
                if val is None:
                    val_str = "(no value)"
                else:
                    val_simp = simplify(val)
                    try:
                        # Try numeric
                        val_float = float(val_simp)
                        val_str = f"{val_float:.10g}"
                    except (TypeError, ValueError):
                        # Keep symbolic
                        val_str = str(val_simp)

                answer_lines.append(f"${sym.name} = {val_str}$")
            except Exception as exc:
                _log(f"Format error for {sym.name}: {exc}")
                answer_lines.append(f"${sym.name} = ?$")

        answer_lines.append("")

    answer_text = "\n".join(answer_lines)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5: Verify
    # ─────────────────────────────────────────────────────────────────────────

    yield {
        "type": "step",
        "title": "Verification",
        "content": "Checking solution..."
    }

    try:
        sol = solutions[0]
        verified = 0
        for eq in sympy_equations:
            result = eq.subs(sol)
            if result == True:
                verified += 1
        
        answer_text += f"\n✓ Solution verified against {verified}/{len(sympy_equations)} equation(s)"
    except Exception as exc:
        _log(f"Verification skipped: {exc}")

    yield {"type": "final", "answer": answer_text}


def _extract_equations_from_text(text: str) -> list[str]:
    """Extract equations from text, handling numbered lists."""
    equations = []

    for line in re.split(r"[\n;]|(?<=\d)\s*\)\s*(?=[a-zA-Z])", text):
        line = line.strip()
        line = re.sub(r"^\s*(?:\d+[\)\.:]|eq\s*\d*\s*:?)\s*", "", line, flags=re.I)

        if not line:
            continue
        if "=" not in line or not re.search(r"[a-zA-Z]", line):
            continue

        equations.append(line)

    return equations
