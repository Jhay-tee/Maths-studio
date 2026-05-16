import asyncio
import sympy as sp
import numpy as np
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
    simplify_math
)

# ── Methods available per problem type ──
SIMULTANEOUS_METHODS = [
    "Substitution Method",
    "Elimination Method",
    "Graphical Method",
    "Matrix Method",
]

SINGLE_EQ_METHODS = [
    "Quadratic Formula",
    "Factorization",
    "Completing the Square",
    "Graphical Method",
]


def _parse_equations(equations_raw, symbols):
    """Parse a list of equation strings into sympy Eq objects."""
    eqs = []
    for eq_text in equations_raw:
        eq_text = clean_math_string(eq_text.strip())
        if not eq_text:
            continue
        if "=" in eq_text:
            parts = eq_text.split("=", 1)
            lhs = simplify_math(safe_sympify(parts[0], symbols=symbols))
            rhs = simplify_math(safe_sympify(parts[1], symbols=symbols))
            eqs.append(sp.Eq(lhs, rhs))
        else:
            eqs.append(sp.Eq(safe_sympify(eq_text, symbols=symbols), 0))
    return eqs


def _latex_eq(eq):
    return f"$${sp.latex(eq)}$$"


# ════════════════════════════════════════════════════
# SIMULTANEOUS EQUATION METHODS
# ════════════════════════════════════════════════════

def _solve_substitution(eqs, symbols, steps):
    """Full substitution method with detailed working."""
    var_list = list(symbols.values())
    steps.append("#### Method: Substitution")
    steps.append("")
    steps.append("**Step 1 — Write the system:**")
    for i, eq in enumerate(eqs, 1):
        steps.append(f"$$\\text{{Eq{i}}}: {sp.latex(eq.lhs)} = {sp.latex(eq.rhs)}$$")
    steps.append("")

    # Try to isolate the first variable from the first equation
    v1, v2 = var_list[0], var_list[1]
    iso_sols = sp.solve(eqs[0], v1)
    if not iso_sols:
        # Try the other variable
        v1, v2 = var_list[1], var_list[0]
        iso_sols = sp.solve(eqs[0], v1)

    if not iso_sols:
        steps.append("Could not isolate a variable analytically. Falling back to symbolic solver.")
        sol = sp.solve(eqs, list(symbols.values()))
        return sol, steps

    iso_expr = iso_sols[0]
    steps.append(f"**Step 2 — Isolate ${sp.latex(v1)}$ from Eq1:**")
    steps.append(f"$${sp.latex(v1)} = {sp.latex(iso_expr)}$$")
    steps.append("")

    # Substitute into Eq2
    subbed = eqs[1].subs(v1, iso_expr)
    subbed_simplified = sp.simplify(subbed)
    steps.append(f"**Step 3 — Substitute into Eq2:**")
    steps.append(f"$${sp.latex(subbed_simplified.lhs)} = {sp.latex(subbed_simplified.rhs)}$$")
    steps.append("")

    # Solve for v2
    v2_sols = sp.solve(subbed_simplified, v2)
    if not v2_sols:
        steps.append(f"Could not solve for ${sp.latex(v2)}$ after substitution.")
        return {}, steps

    v2_val = v2_sols[0]
    steps.append(f"**Step 4 — Solve for ${sp.latex(v2)}$:**")
    steps.append(f"$${sp.latex(v2)} = {sp.latex(v2_val)}$$")
    steps.append("")

    # Back-substitute
    v1_val = sp.simplify(iso_expr.subs(v2, v2_val))
    steps.append(f"**Step 5 — Back-substitute to find ${sp.latex(v1)}$:**")
    steps.append(f"$${sp.latex(v1)} = {sp.latex(sp.simplify(iso_expr))}$$")
    steps.append(f"$${sp.latex(v1)} = {sp.latex(v1_val)}$$")
    steps.append("")

    # Verify
    steps.append("**Step 6 — Verification:**")
    subs_dict = {v1: v1_val, v2: v2_val}
    all_ok = True
    for i, eq in enumerate(eqs, 1):
        lhs_val = sp.simplify(eq.lhs.subs(subs_dict))
        rhs_val = sp.simplify(eq.rhs.subs(subs_dict))
        ok = sp.simplify(lhs_val - rhs_val) == 0
        all_ok = all_ok and ok
        tick = "✓" if ok else "✗"
        steps.append(f"- Eq{i}: ${sp.latex(eq.lhs.subs(subs_dict))} = {sp.latex(eq.rhs.subs(subs_dict))}$ {tick}")
    steps.append("")

    return {v1: v1_val, v2: v2_val}, steps


def _solve_elimination(eqs, symbols, steps):
    """Full elimination method with detailed working."""
    var_list = list(symbols.values())
    steps.append("#### Method: Elimination")
    steps.append("")
    steps.append("**Step 1 — Write the system in standard form:**")
    for i, eq in enumerate(eqs, 1):
        steps.append(f"$$\\text{{Eq{i}}}: {sp.latex(eq.lhs)} = {sp.latex(eq.rhs)}$$")
    steps.append("")

    v1, v2 = var_list[0], var_list[1]
    eq1, eq2 = eqs[0], eqs[1]

    # Get coefficients of v1 in both equations
    poly1 = sp.Poly(eq1.lhs - eq1.rhs, v1)
    poly2 = sp.Poly(eq2.lhs - eq2.rhs, v1)
    c1 = poly1.nth(1) if poly1.degree() >= 1 else sp.Integer(0)
    c2 = poly2.nth(1) if poly2.degree() >= 1 else sp.Integer(0)

    if c1 == 0 or c2 == 0:
        # Try v2
        poly1 = sp.Poly(eq1.lhs - eq1.rhs, v2)
        poly2 = sp.Poly(eq2.lhs - eq2.rhs, v2)
        c1 = poly1.nth(1) if poly1.degree() >= 1 else sp.Integer(0)
        c2 = poly2.nth(1) if poly2.degree() >= 1 else sp.Integer(0)
        eliminate_var = v2
        solve_var = v1
    else:
        eliminate_var = v1
        solve_var = v2

    lcm = sp.lcm(sp.Abs(c1), sp.Abs(c2))
    m1 = sp.simplify(lcm / c1)
    m2 = sp.simplify(lcm / c2)

    steps.append(f"**Step 2 — Identify coefficients of ${sp.latex(eliminate_var)}$:**")
    steps.append(f"- In Eq1: coefficient = ${sp.latex(c1)}$")
    steps.append(f"- In Eq2: coefficient = ${sp.latex(c2)}$")
    steps.append(f"- LCM = ${sp.latex(lcm)}$")
    steps.append("")

    # Multiply equations
    eq1_scaled = sp.Eq(sp.expand(m1 * (eq1.lhs - eq1.rhs) + sp.Integer(0)), sp.Integer(0))
    eq2_scaled = sp.Eq(sp.expand(m2 * (eq2.lhs - eq2.rhs) + sp.Integer(0)), sp.Integer(0))

    # Rewrite as lhs = rhs
    eq1_mult = sp.Eq(sp.expand(m1 * eq1.lhs), sp.expand(m1 * eq1.rhs))
    eq2_mult = sp.Eq(sp.expand(m2 * eq2.lhs), sp.expand(m2 * eq2.rhs))

    steps.append(f"**Step 3 — Multiply to match coefficients:**")
    steps.append(f"- Eq1 × ${sp.latex(m1)}$: $${sp.latex(eq1_mult.lhs)} = {sp.latex(eq1_mult.rhs)}$$")
    steps.append(f"- Eq2 × ${sp.latex(m2)}$: $${sp.latex(eq2_mult.lhs)} = {sp.latex(eq2_mult.rhs)}$$")
    steps.append("")

    # Subtract (or add) to eliminate
    sign = 1 if c1 * c2 > 0 else -1
    combined_lhs = sp.expand(eq1_mult.lhs - sign * eq2_mult.lhs)
    combined_rhs = sp.expand(eq1_mult.rhs - sign * eq2_mult.rhs)
    op = "subtract" if sign == 1 else "add"
    steps.append(f"**Step 4 — {op.capitalize()} to eliminate ${sp.latex(eliminate_var)}$:**")
    steps.append(f"$${sp.latex(combined_lhs)} = {sp.latex(combined_rhs)}$$")
    steps.append("")

    # Solve the single-variable equation
    combined_eq = sp.Eq(combined_lhs, combined_rhs)
    v_sols = sp.solve(combined_eq, solve_var)
    if not v_sols:
        steps.append(f"No solution found for ${sp.latex(solve_var)}$.")
        return {}, steps

    v_val = v_sols[0]
    steps.append(f"**Step 5 — Solve for ${sp.latex(solve_var)}$:**")
    steps.append(f"$${sp.latex(solve_var)} = {sp.latex(v_val)}$$")
    steps.append("")

    # Back-substitute
    back_eq = sp.Eq(eq1.lhs.subs(solve_var, v_val), eq1.rhs.subs(solve_var, v_val))
    elim_sols = sp.solve(back_eq, eliminate_var)
    if not elim_sols:
        steps.append(f"Could not back-substitute for ${sp.latex(eliminate_var)}$.")
        return {}, steps

    elim_val = elim_sols[0]
    steps.append(f"**Step 6 — Substitute ${sp.latex(solve_var)} = {sp.latex(v_val)}$ back into Eq1:**")
    steps.append(f"$${sp.latex(back_eq.lhs)} = {sp.latex(back_eq.rhs)}$$")
    steps.append(f"$${sp.latex(eliminate_var)} = {sp.latex(elim_val)}$$")
    steps.append("")

    # Verify
    subs_dict = {solve_var: v_val, eliminate_var: elim_val}
    steps.append("**Step 7 — Verification:**")
    for i, eq in enumerate(eqs, 1):
        lhs_val = sp.simplify(eq.lhs.subs(subs_dict))
        rhs_val = sp.simplify(eq.rhs.subs(subs_dict))
        ok = sp.simplify(lhs_val - rhs_val) == 0
        tick = "✓" if ok else "✗"
        steps.append(f"- Eq{i}: ${sp.latex(lhs_val)} = {sp.latex(rhs_val)}$ {tick}")
    steps.append("")

    return {solve_var: v_val, eliminate_var: elim_val}, steps


def _solve_matrix_method(eqs, symbols, steps):
    """Matrix / Cramer's Rule method with augmented matrix."""
    var_list = list(symbols.values())
    n = len(var_list)
    steps.append("#### Method: Matrix (Augmented Matrix → Row Reduction)")
    steps.append("")

    steps.append("**Step 1 — Write the system in standard form $Ax = b$:**")
    for i, eq in enumerate(eqs, 1):
        steps.append(f"$$\\text{{Eq{i}}}: {sp.latex(eq.lhs)} = {sp.latex(eq.rhs)}$$")
    steps.append("")

    # Build coefficient matrix A and vector b
    A_rows = []
    b_vals = []
    for eq in eqs:
        expr = sp.expand(eq.lhs - eq.rhs)
        row = []
        for v in var_list:
            coeff = expr.coeff(v)
            row.append(coeff)
        const = -expr.subs({v: 0 for v in var_list})
        A_rows.append(row)
        b_vals.append(const)

    A = sp.Matrix(A_rows)
    b = sp.Matrix(b_vals)

    steps.append("**Step 2 — Coefficient matrix $A$ and constant vector $b$:**")
    steps.append(f"$$A = {sp.latex(A)}, \\quad b = {sp.latex(b)}$$")
    steps.append("")

    # Augmented matrix
    Aug = A.row_join(b)
    steps.append("**Step 3 — Augmented matrix $[A|b]$:**")
    steps.append(f"$$[A|b] = {sp.latex(Aug)}$$")
    steps.append("")

    # Row reduce
    rref_matrix, pivot_cols = Aug.rref()
    steps.append("**Step 4 — Row-reduce to RREF:**")
    steps.append(f"$$\\text{{RREF}} = {sp.latex(rref_matrix)}$$")
    steps.append("")

    # Determinant and invertibility
    det = A.det()
    steps.append(f"**Step 5 — Determinant:** $|A| = {sp.latex(det)}$")
    if det == 0:
        steps.append("**det(A) = 0 → The system has no unique solution (dependent or inconsistent).**")
        return {}, steps
    steps.append("")

    # Cramer's rule for small systems
    if n <= 3:
        steps.append("**Step 6 — Apply Cramer's Rule:**")
        sol_dict = {}
        for i, v in enumerate(var_list):
            Ai = A.copy()
            Ai[:, i] = b
            det_i = Ai.det()
            val = sp.simplify(det_i / det)
            steps.append(f"- ${sp.latex(v)} = \\dfrac{{\\det(A_{{{i+1}}})}}{{{sp.latex(det)}}} = \\dfrac{{{sp.latex(det_i)}}}{{{sp.latex(det)}}} = {sp.latex(val)}$")
            sol_dict[v] = val
        steps.append("")
    else:
        # Solve via matrix inverse
        steps.append("**Step 6 — Solve via $x = A^{-1}b$:**")
        x = A.inv() * b
        sol_dict = {}
        for i, v in enumerate(var_list):
            val = sp.simplify(x[i])
            sol_dict[v] = val
            steps.append(f"- ${sp.latex(v)} = {sp.latex(val)}$")
        steps.append("")

    # Verify
    steps.append("**Step 7 — Verification:**")
    for i, eq in enumerate(eqs, 1):
        lhs_val = sp.simplify(eq.lhs.subs(sol_dict))
        rhs_val = sp.simplify(eq.rhs.subs(sol_dict))
        ok = sp.simplify(lhs_val - rhs_val) == 0
        tick = "✓" if ok else "✗"
        steps.append(f"- Eq{i}: ${sp.latex(lhs_val)} = {sp.latex(rhs_val)}$ {tick}")
    steps.append("")

    return sol_dict, steps


def _solve_graphical(eqs, symbols, steps):
    """Graphical method — express each eq as y = f(x) and produce plot data."""
    var_list = list(symbols.values())
    steps.append("#### Method: Graphical")
    steps.append("")
    steps.append("**Step 1 — Express each equation as $y = f(x)$:**")

    x_var = var_list[0]
    y_var = var_list[1] if len(var_list) > 1 else sp.Symbol('y')
    plot_funcs = []

    for i, eq in enumerate(eqs, 1):
        try:
            y_expr_list = sp.solve(eq, y_var)
            if y_expr_list:
                y_expr = y_expr_list[0]
                steps.append(f"- Eq{i}: $${sp.latex(y_var)} = {sp.latex(y_expr)}$$")
                plot_funcs.append((f"Equation {i}", y_expr, x_var, y_var))
            else:
                steps.append(f"- Eq{i}: Could not express in terms of {y_var}.")
        except Exception:
            steps.append(f"- Eq{i}: Could not rearrange.")

    steps.append("")
    steps.append("**Step 2 — Find intersection analytically:**")
    sol = sp.solve(eqs, list(symbols.values()))
    if isinstance(sol, dict) and sol:
        for v, val in sol.items():
            steps.append(f"- $${sp.latex(v)} = {sp.latex(val)}$$")
        x_num = float(sol.get(x_var, 0))
        y_num = float(sol.get(y_var, 0))
    elif isinstance(sol, list) and sol:
        x_num = float(sol[0][0]) if isinstance(sol[0], (list, tuple)) else 0
        y_num = float(sol[0][1]) if isinstance(sol[0], (list, tuple)) and len(sol[0]) > 1 else 0
        steps.append(f"Intersection at: ({x_num:.4f}, {y_num:.4f})")
    else:
        x_num, y_num = 0, 0
        steps.append("No intersection found.")

    steps.append("")
    steps.append(f"**The intersection point (solution) is at $({sp.latex(x_var)}, {sp.latex(y_var)}) = ({x_num:.4f}, {y_num:.4f})$.**")
    steps.append("")
    steps.append("*See the diagram below for the graphical representation.*")

    # Generate plot data
    x_range = max(abs(x_num) * 3, 10)
    xs = np.linspace(x_num - x_range, x_num + x_range, 300).tolist()
    series_data = []
    for label, y_expr, xv, yv in plot_funcs:
        ys = []
        f = sp.lambdify(xv, y_expr, modules=['numpy'])
        for xval in xs:
            try:
                yval = float(f(xval))
                ys.append(yval if abs(yval) < 1e6 else None)
            except Exception:
                ys.append(None)
        series_data.append({"label": label, "x": xs, "y": ys})

    diagram = {
        "type": "diagram",
        "diagram_type": "line_chart",
        "data": {
            "title": "Graphical Solution — Intersection of Equations",
            "xlabel": str(x_var),
            "ylabel": str(y_var),
            "series": series_data,
            "annotations": [{"x": x_num, "y": y_num, "label": f"Solution ({x_num:.3f}, {y_num:.3f})"}],
            "caption": f"The lines intersect at {x_var}={x_num:.4f}, {y_var}={y_num:.4f}"
        }
    }
    return sol if sol else {}, steps, diagram


# ════════════════════════════════════════════════════
# SINGLE EQUATION METHODS
# ════════════════════════════════════════════════════

def _solve_quadratic_formula(equation, target_var, steps):
    """Apply quadratic formula step by step."""
    expr = equation.lhs - equation.rhs
    try:
        poly = sp.Poly(expr, target_var)
        if poly.degree() != 2:
            return None, steps
        coeffs = poly.all_coeffs()
        if len(coeffs) == 3:
            a, b, c = coeffs
        elif len(coeffs) == 2:
            a, b, c = coeffs[0], coeffs[1], sp.Integer(0)
        else:
            return None, steps
    except Exception:
        return None, steps

    steps.append("#### Method: Quadratic Formula")
    steps.append("")
    steps.append(f"**Standard form:** $${sp.latex(a)}{sp.latex(target_var)}^2 + ({sp.latex(b)}){sp.latex(target_var)} + ({sp.latex(c)}) = 0$$")
    steps.append(f"**Coefficients:** $a = {sp.latex(a)},\\quad b = {sp.latex(b)},\\quad c = {sp.latex(c)}$")
    discriminant = b**2 - 4*a*c
    steps.append(f"")
    steps.append(f"**Step 1 — Discriminant:**")
    steps.append(f"$$\\Delta = b^2 - 4ac = ({sp.latex(b)})^2 - 4({sp.latex(a)})({sp.latex(c)}) = {sp.latex(discriminant)}$$")
    steps.append("")

    disc_simplified = sp.simplify(discriminant)
    disc_val = float(disc_simplified) if disc_simplified.is_number else None

    if disc_val is not None:
        if disc_val > 0:
            steps.append(f"$\\Delta = {sp.latex(disc_simplified)} > 0$ → Two distinct real roots")
        elif disc_val == 0:
            steps.append(f"$\\Delta = 0$ → One repeated real root")
        else:
            steps.append(f"$\\Delta = {sp.latex(disc_simplified)} < 0$ → Two complex conjugate roots")
    steps.append("")

    steps.append("**Step 2 — Apply formula $x = \\dfrac{{-b \\pm \\sqrt{{\\Delta}}}}{{2a}}$:**")
    root1_expr = (-b + sp.sqrt(discriminant)) / (2 * a)
    root2_expr = (-b - sp.sqrt(discriminant)) / (2 * a)
    r1 = sp.simplify(root1_expr)
    r2 = sp.simplify(root2_expr)
    steps.append(f"$$x_1 = \\frac{{-({sp.latex(b)}) + \\sqrt{{{sp.latex(discriminant)}}}}}{{2({sp.latex(a)})}} = {sp.latex(r1)}$$")
    steps.append(f"$$x_2 = \\frac{{-({sp.latex(b)}) - \\sqrt{{{sp.latex(discriminant)}}}}}{{2({sp.latex(a)})}} = {sp.latex(r2)}$$")
    steps.append("")

    sols = [r1] if r1 == r2 else [r1, r2]
    return sols, steps


def _solve_completing_square(equation, target_var, steps):
    """Complete the square step by step."""
    expr = equation.lhs - equation.rhs
    try:
        poly = sp.Poly(expr, target_var)
        if poly.degree() != 2:
            return None, steps
        coeffs = poly.all_coeffs()
        a, b, c = coeffs[0], coeffs[1], coeffs[2]
    except Exception:
        return None, steps

    steps.append("#### Method: Completing the Square")
    steps.append("")
    steps.append(f"**Starting equation:** $${sp.latex(a)}{sp.latex(target_var)}^2 + ({sp.latex(b)}){sp.latex(target_var)} + ({sp.latex(c)}) = 0$$")
    steps.append("")

    if a != 1:
        steps.append(f"**Step 1 — Divide through by $a = {sp.latex(a)}$:**")
        b_a = sp.Rational(b, a) if isinstance(a, sp.Integer) and isinstance(b, sp.Integer) else b/a
        c_a = sp.Rational(c, a) if isinstance(a, sp.Integer) and isinstance(c, sp.Integer) else c/a
        steps.append(f"$${sp.latex(target_var)}^2 + ({sp.latex(b_a)}){sp.latex(target_var)} + ({sp.latex(c_a)}) = 0$$")
    else:
        b_a, c_a = b, c
        steps.append("**Step 1 — Coefficient $a = 1$, no division needed.**")
    steps.append("")

    half_b = sp.simplify(b_a / 2)
    half_b_sq = sp.simplify(half_b**2)
    steps.append(f"**Step 2 — Find $(\\frac{{b}}{{2}})^2$:**")
    steps.append(f"$$\\left(\\frac{{{sp.latex(b_a)}}}{{2}}\\right)^2 = ({sp.latex(half_b)})^2 = {sp.latex(half_b_sq)}$$")
    steps.append("")

    steps.append(f"**Step 3 — Add and subtract $({sp.latex(half_b_sq)})$ on the left:**")
    rhs_val = sp.simplify(half_b_sq - c_a)
    steps.append(f"$$({sp.latex(target_var)} + {sp.latex(half_b)})^2 = {sp.latex(rhs_val)}$$")
    steps.append("")

    steps.append(f"**Step 4 — Take square root of both sides:**")
    steps.append(f"$${sp.latex(target_var)} + {sp.latex(half_b)} = \\pm\\sqrt{{{sp.latex(rhs_val)}}}$$")
    steps.append("")

    root_val = sp.sqrt(rhs_val)
    r1 = sp.simplify(-half_b + root_val)
    r2 = sp.simplify(-half_b - root_val)
    steps.append(f"**Step 5 — Solve for ${sp.latex(target_var)}$:**")
    steps.append(f"$${sp.latex(target_var)}_1 = {sp.latex(r1)}, \\quad {sp.latex(target_var)}_2 = {sp.latex(r2)}$$")
    steps.append("")

    return [r1, r2], steps


def _solve_factorization(equation, target_var, steps):
    """Factorization method."""
    expr = equation.lhs - equation.rhs
    steps.append("#### Method: Factorization")
    steps.append("")
    steps.append(f"**Expression:** $${sp.latex(expr)} = 0$$")
    steps.append("")

    steps.append("**Step 1 — Factor the expression:**")
    factored = sp.factor(expr)
    steps.append(f"$${sp.latex(factored)} = 0$$")
    steps.append("")

    steps.append("**Step 2 — Set each factor equal to zero:**")
    factors = sp.factor_list(expr)[1]
    sols = []
    for factor, mult in factors:
        factor_sols = sp.solve(sp.Eq(factor, 0), target_var)
        for s in factor_sols:
            steps.append(f"- ${sp.latex(factor)} = 0 \\Rightarrow {sp.latex(target_var)} = {sp.latex(s)}$")
            sols.append(s)
    steps.append("")

    if not sols:
        sols = sp.solve(equation, target_var)
        for s in sols:
            steps.append(f"- ${sp.latex(target_var)} = {sp.latex(s)}$")

    return sols, steps


# ════════════════════════════════════════════════════
# MAIN SOLVER
# ════════════════════════════════════════════════════

async def solve_algebra(data):
    yield {"type": "step", "content": "Initializing Algebra Engine..."}

    params = data.get("parameters", {})
    expr_str = params.get("expression", data.get("raw_query", ""))
    expr_str = clean_math_string(expr_str)
    requested_method = (data.get("requested_method") or params.get("method") or "").strip()

    # ── Uncertainty propagation ──
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
            pass

    if not expr_str:
        yield {"type": "final", "answer": "Error: No algebraic expression found to solve."}
        return

    yield {"type": "step", "content": f"Parsing expression(s)..."}

    try:
        vars_detected = detect_variables(expr_str)
        if not vars_detected:
            vars_detected = ["x"]

        yield {"type": "step", "content": f"Variables detected: {', '.join(vars_detected)}"}

        symbols = {v: sp.Symbol(v) for v in vars_detected}

        # ── Matrix detection ──
        if detect_matrix(expr_str):
            yield {"type": "step", "content": "Matrix detected — running linear algebra analysis..."}
            M = parse_matrix(expr_str)
            if M:
                rows, cols = M.shape
                steps = ["### Matrix Analysis"]
                steps.append(f"Matrix $M = {sp.latex(M)}$")
                steps.append(f"**Dimensions:** ${rows} \\times {cols}$")

                yield {
                    "type": "diagram",
                    "diagram_type": "matrix",
                    "data": {
                        "rows": rows, "cols": cols,
                        "values": M.tolist(),
                        "caption": "Parsed Matrix structure."
                    }
                }

                if rows == cols:
                    det = M.det()
                    steps.append(f"**Determinant:** $|M| = {sp.latex(det)}$")
                    if det != 0:
                        inv = M.inv()
                        steps.append(f"**Inverse:** $M^{{-1}} = {sp.latex(inv)}$")
                    if rows <= 4:
                        eigs = M.eigenvals()
                        steps.append("**Eigenvalues:**")
                        for e, m in eigs.items():
                            steps.append(f"- $\\lambda = {sp.latex(e)}$ (multiplicity: {m})")
                        eigvecs = M.eigenvects()
                        steps.append("**Eigenvectors:**")
                        for eigval, mult, vecs in eigvecs:
                            for vec in vecs:
                                steps.append(f"- $\\lambda={sp.latex(eigval)}$: $v = {sp.latex(vec)}$")
                    rank = M.rank()
                    steps.append(f"**Rank:** {rank}")

                yield {"type": "final", "answer": "\n".join(steps)}
                return

        # ── Split equations ──
        delimiters = [";", "\n", " and "]
        equations_raw = [expr_str]
        for d in delimiters:
            if d.lower() in expr_str.lower():
                pattern = re.compile(re.escape(d), re.IGNORECASE)
                equations_raw = [e.strip() for e in pattern.split(expr_str) if e.strip()]
                break

        if len(equations_raw) == 1 and "," in expr_str and expr_str.count("=") > 1:
            equations_raw = [e.strip() for e in expr_str.split(",") if e.strip()]

        # ── Simultaneous Equations ──
        is_simultaneous = len(equations_raw) > 1

        if is_simultaneous:
            yield {"type": "step", "content": f"Detected {len(equations_raw)} simultaneous equations."}

            # Parse all equations
            eqs = _parse_equations(equations_raw, symbols)
            if not eqs:
                yield {"type": "final", "answer": "Could not parse the equations. Please check the format."}
                return

            yield {"type": "step", "content": f"Equations parsed successfully. Applying {requested_method or 'optimal method'}..."}

            # Method detection from requested_method string
            method_lower = requested_method.lower() if requested_method else ""
            use_substitution = any(k in method_lower for k in ["substitut"])
            use_elimination = any(k in method_lower for k in ["eliminat"])
            use_graphical = any(k in method_lower for k in ["graph"])
            use_matrix = any(k in method_lower for k in ["matrix", "cramer"])

            steps = [
                "### Simultaneous Equations Solution",
                f"**System:** {len(eqs)} equations, {len(symbols)} unknowns",
                "",
            ]

            diagram_to_emit = None

            if use_graphical and len(vars_detected) >= 2:
                sol, steps, diagram_to_emit = _solve_graphical(eqs, symbols, steps)
            elif use_matrix:
                sol, steps = _solve_matrix_method(eqs, symbols, steps)
            elif use_elimination:
                sol, steps = _solve_elimination(eqs, symbols, steps)
            elif use_substitution:
                sol, steps = _solve_substitution(eqs, symbols, steps)
            else:
                # Auto: use substitution for 2×2, matrix for larger
                if len(eqs) == 2 and len(vars_detected) == 2:
                    sol, steps = _solve_substitution(eqs, symbols, steps)
                else:
                    sol, steps = _solve_matrix_method(eqs, symbols, steps)

            # Final answer block
            steps.append("---")
            steps.append("#### Summary of Results")
            if not sol:
                steps.append("**No unique solution found.**")
                steps.append("The system may be inconsistent (no solution) or dependent (infinitely many solutions).")
            elif isinstance(sol, dict):
                for var, val in sorted(sol.items(), key=lambda x: str(x[0])):
                    num_val = sp.simplify(val)
                    if num_val.is_number:
                        float_val = float(num_val)
                        steps.append(f"$$\\boxed{{{sp.latex(var)} = {sp.latex(num_val)} \\approx {float_val:.6g}}}$$")
                    else:
                        steps.append(f"$$\\boxed{{{sp.latex(var)} = {sp.latex(num_val)}}}$$")
            elif isinstance(sol, list):
                for idx, s in enumerate(sol):
                    steps.append(f"**Solution {idx+1}:** {sp.latex(s)}")

            if diagram_to_emit:
                yield diagram_to_emit

            yield {"type": "final", "answer": "\n".join(steps)}
            return

        # ── Single Equation ──
        eq_text = clean_math_string(equations_raw[0])
        if "=" in eq_text:
            parts = eq_text.split("=", 1)
            lhs = simplify_math(safe_sympify(parts[0], symbols=symbols))
            rhs = simplify_math(safe_sympify(parts[1], symbols=symbols))
            equation = sp.Eq(lhs, rhs)
        else:
            equation = sp.Eq(safe_sympify(eq_text, symbols=symbols), 0)

        target_var = symbols[vars_detected[0]] if vars_detected else sp.Symbol('x')

        # Check for factorization request
        lowered_query = data.get("raw_query", "").lower()
        is_factorization = "factor" in lowered_query or "factoris" in lowered_query

        if is_factorization:
            yield {"type": "step", "content": "Factorization requested..."}
            expr_to_factor = equation.lhs - equation.rhs
            steps = ["### Factorization"]
            steps.append(f"**Expression:** $${sp.latex(expr_to_factor)}$$")
            steps.append("")
            factored = sp.factor(expr_to_factor)
            steps.append(f"**Factored Form:** $${sp.latex(factored)}$$")
            roots = sp.solve(expr_to_factor, target_var)
            if roots:
                steps.append("**Roots:**")
                for r in roots:
                    steps.append(f"- $${sp.latex(target_var)} = {sp.latex(r)}$$")
            yield {"type": "final", "answer": "\n".join(steps)}
            return

        # Detect degree
        expr_for_poly = equation.lhs - equation.rhs
        is_quadratic = False
        try:
            poly = sp.Poly(expr_for_poly, target_var)
            is_quadratic = poly.degree() == 2
        except Exception:
            pass

        method_lower = requested_method.lower() if requested_method else ""

        steps = ["### Algebraic Resolution", f"**Equation:** $${sp.latex(equation)}$$", ""]

        solutions = None

        if is_quadratic:
            yield {"type": "step", "content": "Quadratic equation detected..."}
            if "completing" in method_lower or "square" in method_lower:
                solutions, steps = _solve_completing_square(equation, target_var, steps)
            elif "factor" in method_lower:
                solutions, steps = _solve_factorization(equation, target_var, steps)
            elif "quadratic" in method_lower or "formula" in method_lower:
                solutions, steps = _solve_quadratic_formula(equation, target_var, steps)
            else:
                # Default: quadratic formula for step-by-step clarity
                solutions, steps = _solve_quadratic_formula(equation, target_var, steps)
        else:
            yield {"type": "step", "content": f"Solving for ${target_var}$..."}
            solutions = sp.solve(equation, target_var)
            if not solutions:
                steps.append("No analytical solution found. The equation may have no real solutions.")
            else:
                steps.append("#### Solution Steps")
                steps.append(f"Rearranging and solving for ${sp.latex(target_var)}$:")
                for idx, sol in enumerate(solutions):
                    steps.append(f"$$\\boxed{{{sp.latex(target_var)} = {sp.latex(sol)}}}$$")

        # Final answer box
        steps.append("")
        steps.append("---")
        steps.append("#### Final Answer")
        if solutions:
            for idx, sol in enumerate(solutions if isinstance(solutions, list) else [solutions]):
                num = sp.simplify(sol)
                if num.is_number:
                    steps.append(f"$$\\boxed{{{sp.latex(target_var)} = {sp.latex(num)} \\approx {float(num):.6g}}}$$")
                else:
                    steps.append(f"$$\\boxed{{{sp.latex(target_var)} = {sp.latex(num)}}}$$")
        else:
            steps.append("No real solutions found.")

        yield {"type": "final", "answer": "\n".join(steps)}

    except Exception as e:
        yield {"type": "final", "answer": f"Algebraic Error: Could not parse or solve this expression.\n\n**Details:** {str(e)}\n\nPlease verify the expression format (use standard math notation, e.g. `2*x + 3*y = 7`)."}
