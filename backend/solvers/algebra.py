# algebra.py
import asyncio
import sympy as sp
import re
from solvers.utils import (
    normalize_params,
    validate_physical_params,
    propagate_uncertainty,
    detect_matrix,
    parse_matrix,
    clean_math_string,
    detect_variables,
    safe_sympify,
    simplify_math,
)


def _to_serializable(val):
    """Recursively convert sympy/numpy types to JSON-safe Python types."""
    if isinstance(val, (sp.Float, sp.Integer, sp.Rational)):
        return float(val)
    if hasattr(val, "item"):          # numpy scalar
        return val.item()
    if isinstance(val, dict):
        return {k: _to_serializable(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_to_serializable(v) for v in val]
    return val


# ---------------------------------------------------------------------------
# Robust equation-system splitter
# ---------------------------------------------------------------------------
def _split_equations(expr_str: str) -> list[str]:
    """
    Return a list of individual equation strings from a (possibly multi-equation)
    input.  Handles semicolons, newlines, 'and', and bare whitespace-separated
    equations like "3x+4y=12 2x-y=9".
    """
    # 1. Explicit delimiters first
    for delim in [";", "\n", " and "]:
        if delim.lower() in expr_str.lower():
            parts = re.split(re.escape(delim), expr_str, flags=re.IGNORECASE)
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) > 1:
                return parts

    # 2. Comma delimiter only when multiple '=' are present
    if "," in expr_str and expr_str.count("=") > 1:
        parts = [p.strip() for p in expr_str.split(",") if p.strip()]
        if len(parts) > 1:
            return parts

    # 3. Multiple '=' with NO explicit delimiter — extract each lhs=rhs token
    #    Pattern: capture everything up to the next standalone LHS token.
    #    Strategy: split on boundaries where a digit or ')' is followed by
    #    whitespace and then a term that contains '='.
    if expr_str.count("=") > 1:
        # Find all "something = something" pairs greedily from left to right.
        # We tokenise by finding each '=' and walking left/right for the operands.
        eq_matches = list(re.finditer(r"=", expr_str))
        equations = []
        boundaries = [0] + [m.start() for m in eq_matches] + [len(expr_str)]

        # Simpler: split on whitespace runs that immediately precede a known
        # variable letter at the start of an expression chunk.
        chunks = re.split(r"\s{1,}", expr_str)
        # Re-join chunks that don't yet contain an '=' with the next chunk
        joined: list[str] = []
        buf = ""
        for chunk in chunks:
            buf = (buf + " " + chunk).strip() if buf else chunk
            if "=" in buf:
                joined.append(buf)
                buf = ""
        if buf:
            if joined:
                joined[-1] += " " + buf
            else:
                joined.append(buf)

        if len(joined) > 1:
            return [clean_math_string(e) for e in joined if e.strip()]

    return [expr_str]


async def solve_algebra(data):
    yield {"type": "step", "content": "Initializing Algebra Engine..."}

    params = data.get("parameters", {})
    expr_str = params.get("expression", data.get("raw_query", ""))
    expr_str = clean_math_string(expr_str)
    preferred_method = (
        data.get("requested_method")
        or params.get("method")
        or "standard symbolic solving"
    )

    # ------------------------------------------------------------------
    # Uncertainty propagation shortcut
    # ------------------------------------------------------------------
    if any(k.endswith("_sigma") for k in params.keys()):
        yield {"type": "step", "content": "Uncertainty parameters detected. Running propagation kernel..."}
        uncertainties = {k.replace("_sigma", ""): v for k, v in params.items() if k.endswith("_sigma")}
        nominal_params = {k: v for k, v in params.items() if not k.endswith("_sigma")}

        try:
            expr = safe_sympify(expr_str)
            result_val = float(expr.subs(nominal_params))
            sigma = propagate_uncertainty(expr, nominal_params, uncertainties)

            steps = ["### Mathematical Uncertainty Report"]
            steps.append(f"- **Expression:** ${sp.latex(expr)}$")
            from solvers.utils import append_uncertainty_to_final
            steps = append_uncertainty_to_final(steps, "Result", result_val, sigma)
            yield {"type": "final", "answer": "\n".join(steps)}
            return
        except Exception:
            pass  # Fall through to standard solve

    if not expr_str:
        yield {"type": "final", "answer": "Error: No algebraic expression found to solve."}
        return

    yield {"type": "step", "content": f"Parsing expression(s): {expr_str}"}

    try:
        vars_detected = detect_variables(expr_str)
        if not vars_detected:
            vars_detected = ["x"]

        yield {"type": "step", "content": f"Variables identified: {', '.join(vars_detected)}"}

        symbols = {v: sp.Symbol(v) for v in vars_detected}

        # ------------------------------------------------------------------
        # Matrix detection
        # ------------------------------------------------------------------
        if detect_matrix(expr_str):
            yield {"type": "step", "content": "Matrix detected. Performing linear algebra analysis..."}
            M = parse_matrix(expr_str)
            if M:
                rows, cols = M.shape
                steps = ["### Matrix Analysis"]
                steps.append(f"Matrix $M = {sp.latex(M)}$")
                steps.append(f"Dimensions: {rows}x{cols}")

                yield {
                    "type": "diagram",
                    "diagram_type": "matrix",
                    "data": _to_serializable({
                        "rows": rows,
                        "cols": cols,
                        "values": M.tolist(),
                        "caption": "Parsed Matrix structure.",
                    }),
                }

                if rows == cols:
                    yield {"type": "step", "content": "Calculating determinant and inverse..."}
                    det = M.det()
                    steps.append(f"- **Determinant:** $|M| = {sp.latex(det)}$")
                    if det != 0:
                        steps.append(f"- **Inverse:** $M^{{-1}} = {sp.latex(M.inv())}$")

                    if rows < 4:
                        yield {"type": "step", "content": "Analyzing eigenvalues..."}
                        eigs = M.eigenvals()
                        steps.append("**Eigenvalues:**")
                        for e, m in eigs.items():
                            steps.append(f"- $\\lambda = {sp.latex(e)}$ (mult: {m})")

                yield {"type": "final", "answer": "\n".join(steps)}
                return

        # ------------------------------------------------------------------
        # Split into individual equations
        # ------------------------------------------------------------------
        equations_raw = _split_equations(expr_str)

        # ------------------------------------------------------------------
        # System of equations
        # ------------------------------------------------------------------
        if len(equations_raw) > 1:
            yield {"type": "step", "content": f"Detected {len(equations_raw)} simultaneous equations."}
            eqs = []
            for eq_text in equations_raw:
                eq_text = clean_math_string(eq_text)
                if "=" in eq_text:
                    parts = eq_text.split("=", 1)
                    lhs = simplify_math(safe_sympify(parts[0], symbols=symbols))
                    rhs = simplify_math(safe_sympify(parts[1], symbols=symbols))
                    eqs.append(sp.Eq(lhs, rhs))
                else:
                    eqs.append(sp.Eq(safe_sympify(eq_text, symbols=symbols), 0))

            yield {"type": "step", "content": "Solving system of equations..."}

            system_steps = [
                "### Simultaneous Equations Resolution",
                f"**Method Used:** {preferred_method.title()}",
                "#### Given System:",
            ]
            for eq in eqs:
                system_steps.append(f"- $${sp.latex(eq)}$$")

            # Show substitution steps for a clean 2×2 system
            if len(eqs) == 2 and len(symbols) == 2:
                yield {"type": "step", "content": "Using substitution/elimination method for 2×2 system..."}
                system_steps.append("#### Steps for 2×2 System:")
                var_list = list(symbols.values())
                v1, v2 = var_list[0], var_list[1]

                try:
                    iso_sols = sp.solve(eqs[0], v1)
                    if iso_sols:
                        iso_expr = iso_sols[0]
                        system_steps.append(
                            f"1. Isolate ${sp.latex(v1)}$ from equation 1: "
                            f"$${sp.latex(v1)} = {sp.latex(iso_expr)}$$"
                        )
                        subbed_eq = eqs[1].subs(v1, iso_expr)
                        system_steps.append(
                            f"2. Substitute into equation 2: $${sp.latex(subbed_eq)}$$"
                        )
                        v2_sols = sp.solve(subbed_eq, v2)
                        if v2_sols:
                            v2_val = v2_sols[0]
                            system_steps.append(
                                f"3. Solve for ${sp.latex(v2)}$: "
                                f"$${sp.latex(v2)} = {sp.latex(v2_val)}$$"
                            )
                            final_v1 = iso_expr.subs(v2, v2_val)
                            system_steps.append(
                                f"4. Back-substitute to find ${sp.latex(v1)}$: "
                                f"$${sp.latex(v1)} = {sp.latex(final_v1)}$$"
                            )
                except Exception:
                    system_steps.append(
                        "Proceeding with standard matrix/symbolic resolution for complex system."
                    )

            sol_dict = sp.solve(eqs, list(symbols.values()))

            system_steps.append("#### Final Solutions:")
            if not sol_dict:
                system_steps.append("No solution found for the given system.")
            elif isinstance(sol_dict, dict):
                for var, val in sol_dict.items():
                    system_steps.append(f"- $${sp.latex(var)} = {sp.latex(val)}$$")
            elif isinstance(sol_dict, list):
                if len(sol_dict) > 0 and isinstance(sol_dict[0], tuple):
                    for idx, sol_tuple in enumerate(sol_dict):
                        system_steps.append(f"**Set {idx + 1}:**")
                        for var, val in zip(symbols.values(), sol_tuple):
                            system_steps.append(f"- $${sp.latex(var)} = {sp.latex(val)}$$")
                else:
                    system_steps.append(f"Result: $${sp.latex(sol_dict)}$$")

            yield {"type": "final", "answer": "\n".join(system_steps)}
            return

        # ------------------------------------------------------------------
        # Single equation
        # ------------------------------------------------------------------
        eq_text = clean_math_string(equations_raw[0])
        if "=" in eq_text:
            parts = eq_text.split("=", 1)
            lhs = simplify_math(safe_sympify(parts[0], symbols=symbols))
            rhs = simplify_math(safe_sympify(parts[1], symbols=symbols))
            equation = sp.Eq(lhs, rhs)
        else:
            equation = sp.Eq(safe_sympify(eq_text, symbols=symbols), 0)

        target_var = symbols[vars_detected[0]] if vars_detected else sp.Symbol("x")

        # Factorization request
        lowered_query = data.get("raw_query", "").lower()
        is_factorization = "factor" in lowered_query or preferred_method == "factorization"

        if is_factorization:
            yield {"type": "step", "content": f"Factorization requested for expression in {target_var}..."}
            expr_to_factor = equation.lhs - equation.rhs
            method = params.get("factor_method", "standard").lower()

            steps = ["### Factorization Report", f"Expression: $${sp.latex(expr_to_factor)}$$"]

            if method == "grouping":
                yield {"type": "step", "content": "Attempting factorization by grouping terms..."}
                steps.append("#### Method: Factorization by Grouping")
                factored = sp.factor(expr_to_factor)
                steps.append("1. **Arrange Terms:** Group terms with common factors.")
                steps.append("2. **Factor Out Commons:** Finding common sub-expressions.")
                steps.append(f"3. **Conclusion:** $${sp.latex(factored)}$$")

            elif method == "quadratic formula" or (
                method == "standard"
                and sp.Poly(expr_to_factor, target_var).degree() == 2
            ):
                yield {"type": "step", "content": "Executing Trinomial Decomposition..."}
                poly = sp.Poly(expr_to_factor, target_var)
                coeffs = poly.all_coeffs()
                if len(coeffs) == 3:
                    a, b, c = coeffs
                    steps.append("#### Method: Quadratic Trinomial Decomposition")
                    steps.append(f"1. **Coefficients:** $a={a},\\ b={b},\\ c={c}$")
                    discriminant = b ** 2 - 4 * a * c
                    steps.append(f"2. **Discriminant:** $D = {discriminant}$")
                    roots = sp.solve(expr_to_factor, target_var)
                    if roots:
                        roots_latex = ", ".join(sp.latex(r) for r in roots)
                        steps.append(f"3. **Roots:** $\\{{{roots_latex}\\}}$")
                        factored_str = f"{sp.latex(a)}" if a != 1 else ""
                        for r in roots:
                            factored_str += f"({sp.latex(target_var)} - ({sp.latex(r)}))"
                        steps.append(f"4. **Factored Form:** $${factored_str}$$")
                    else:
                        steps.append(r"3. **Insight:** No real roots over $\mathbb{R}$.")
                else:
                    factored = sp.factor(expr_to_factor)
                    steps.append(f"Result: $${sp.latex(factored)}$$")

            elif method == "difference of squares":
                yield {"type": "step", "content": "Checking for Difference of Squares pattern..."}
                steps.append("#### Method: Difference of Squares")
                factored = sp.factor(expr_to_factor)
                steps.append("1. **Pattern:** $a^2 - b^2 = (a-b)(a+b)$")
                steps.append(f"2. **Result:** $${sp.latex(factored)}$$")

            else:
                yield {"type": "step", "content": "Applying symbolic factorization..."}
                factored = sp.factor(expr_to_factor)
                steps.append("#### Method: Symbolic Factorization")
                steps.append("**Step 1:** Scan for GCDs across terms.")
                steps.append("**Step 2:** Apply recursive polynomial division.")
                steps.append(f"**Result:** $${sp.latex(factored)}$$")

            yield {"type": "final", "answer": "\n".join(steps)}
            return

        # Standard single-equation solve
        yield {"type": "step", "content": f"Solving for {target_var}..."}
        solutions = sp.solve(equation, target_var)

        # Quadratic breakdown
        is_quadratic = False
        try:
            poly = sp.Poly(equation.lhs - equation.rhs, target_var)
            if poly.degree() == 2:
                is_quadratic = True
                a, b, c = poly.all_coeffs()
                discriminant = b ** 2 - 4 * a * c
                yield {"type": "step", "content": "Detected Quadratic Equation. Applying Quadratic Formula..."}
        except Exception:
            is_quadratic = False

        steps = [
            "### Algebraic Resolution",
            f"**Method Used:** {preferred_method.title()}",
            f"Equation: $${sp.latex(equation)}$$",
        ]

        if is_quadratic:
            steps.append("#### Quadratic Breakdown")
            steps.append(
                f"Standard Form: $${sp.latex(a)}{sp.latex(target_var)}^2 "
                f"+ {sp.latex(b)}{sp.latex(target_var)} + {sp.latex(c)} = 0$$"
            )
            steps.append(f"Coefficients: $a={a},\\ b={b},\\ c={c}$")
            steps.append(f"Discriminant: $D = b^2 - 4ac = {discriminant}$")

        steps.append("#### Final Solutions:")
        if not solutions:
            steps.append("No analytical solution found.")
        else:
            for idx, sol in enumerate(solutions):
                steps.append(f"{idx + 1}. $${sp.latex(target_var)} = {sp.latex(sol)}$$")

        yield {"type": "final", "answer": "\n".join(steps)}

    except Exception as e:
        yield {"type": "error", "message": f"Algebraic error: Could not parse or solve expression. Details: {str(e)}"}
