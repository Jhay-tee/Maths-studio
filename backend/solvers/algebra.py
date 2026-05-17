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
    Solve algebraic equations with robust symbol mapping.
    """
    params = sub.get("parameters", {})
    raw_query = sub.get("raw_query", "")

    yield {
        "type": "step",
        "title": "Input validation",
        "content": "Extracting variables and parsing equations..."
    }

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: Extract equations from parameters or raw text
    # ─────────────────────────────────────────────────────────────────────────
    equations_list = []
    if "equations" in params and isinstance(params["equations"], list):
        equations_list = [str(e).strip() for e in params["equations"] if e]
    elif "expression" in params and params["expression"]:
        equations_list = [str(params["expression"]).strip()]
    
    if not equations_list:
        equations_list = _extract_equations_from_text(raw_query)

    if not equations_list:
        yield {
            "type": "final",
            "answer": "**Error:** No equations found. Please use `x + y = 10` format."
        }
        return

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: Unified Symbol Mapping (The Fix)
    # ─────────────────────────────────────────────────────────────────────────
    # Identify all single-letter variables across all equations
    all_var_names = set()
    for eq_str in equations_list:
        vars_found = re.findall(r"\b([a-zA-Z])\b", eq_str)
        all_var_names.update(vars_found)

    if not all_var_names:
        yield {
            "type": "final",
            "answer": "**Error:** No variables detected (e.g., x, y)."
        }
        return

    # Create a local dictionary mapping strings to SymPy Symbols
    # This ensures sympify() uses the exact same objects as the solver
    local_dict = {name: sp.Symbol(name, real=True) for name in all_var_names}
    var_symbols = sorted(local_dict.values(), key=lambda s: s.name)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: Parse Strings into SymPy Equations
    # ─────────────────────────────────────────────────────────────────────────
    sympy_equations = []
    try:
        for eq_str in equations_list:
            if "=" in eq_str:
                lhs_str, rhs_str = eq_str.split("=", 1)
                lhs = sympify(lhs_str.strip(), locals=local_dict)
                rhs = sympify(rhs_str.strip(), locals=local_dict)
                sympy_equations.append(Eq(lhs, rhs))
            else:
                expr = sympify(eq_str.strip(), locals=local_dict)
                sympy_equations.append(Eq(expr, 0))
        _log(f"Parsed {len(sympy_equations)} equations with variables: {all_var_names}")
    except Exception as exc:
        yield {
            "type": "final",
            "answer": f"**Parsing error:** `{str(exc)}`"
        }
        return

    yield {
        "type": "step",
        "title": "System detected",
        "content": f"**Variables:** {', '.join(sorted(all_var_names))}\n**Equations:** {len(sympy_equations)}"
    }

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: Solve
    # ─────────────────────────────────────────────────────────────────────────
    yield {
        "type": "step",
        "title": "Solving",
        "content": "Computing solution..."
    }

    try:
        # dict=True returns a list of dictionaries mapping Symbol: value
        solutions = solve(sympy_equations, var_symbols, dict=True)

        if not solutions:
            yield {
                "type": "final",
                "answer": "**No solution found.**\n\nThe system may be inconsistent or dependent."
            }
            return

    except Exception as exc:
        yield {
            "type": "final",
            "answer": f"**Solver error:** {str(exc)}"
        }
        return

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5: Format Answer
    # ─────────────────────────────────────────────────────────────────────────
    answer_lines = []
    for i, sol_dict in enumerate(solutions):
        header = f"### Solution {i+1}" if len(solutions) > 1 else "### Solution"
        answer_lines.append(header)
        
        for sym in var_symbols:
            val = sol_dict.get(sym)
            if val is not None:
                val_simp = simplify(val)
                # Attempt to convert to clean float if numeric, else keep symbolic
                try:
                    if val_simp.is_number:
                        f_val = float(val_simp)
                        # Format to 10 decimal places but strip trailing zeros
                        val_str = f"{f_val:.10g}"
                    else:
                        val_str = str(val_simp)
                except:
                    val_str = str(val_simp)
                
                answer_lines.append(f"**{sym.name}** = `{val_str}`")
            else:
                answer_lines.append(f"**{sym.name}** = (undetermined)")
        answer_lines.append("")

    # Verification Logic
    try:
        test_sol = solutions[0]
        verified_count = 0
        for eq in sympy_equations:
            # check if lhs - rhs == 0
            if simplify(eq.lhs.subs(test_sol) - eq.rhs.subs(test_sol)) == 0:
                verified_count += 1
        
        verification_msg = f"\n\n---\n✓ Verified: Correct for {verified_count}/{len(sympy_equations)} equations."
        final_answer = "\n".join(answer_lines) + verification_msg
    except:
        final_answer = "\n".join(answer_lines)

    yield {"type": "final", "answer": final_answer}

def _extract_equations_from_text(text: str) -> list[str]:
    """Helper to clean up raw user queries into a list of equation strings."""
    equations = []
    # Split by newline or semicolon
    lines = re.split(r"[\n;]", text)
    for line in lines:
        clean = line.strip()
        # Remove leading list markers like "1)" or "eq 1:"
        clean = re.sub(r"^\s*(?:\d+[\)\.:]|eq\s*\d*\s*:?)\s*", "", clean, flags=re.I)
        if clean and ("=" in clean or re.search(r"[a-zA-Z]", clean)):
            equations.append(clean)
    return equations
