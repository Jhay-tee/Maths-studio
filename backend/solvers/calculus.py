"""
Advanced Calculus Solver
Handles: Taylor series, gradient, multiple integration, partial derivatives,
         ODEs, Fourier series, and general differentiation / integration.
"""

import asyncio
import sympy as sp
from solvers.utils import safe_sympify, clean_math_string, simplify_math, detect_variables


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _latex_block(expr):
    """Wrap a sympy expression in a LaTeX display block."""
    return f"$${sp.latex(expr)}$$"


def _keyword_in(needle, *haystacks):
    return any(needle in h for h in haystacks)


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

async def solve_calculus(data):
    yield {"type": "step", "content": "Initializing Advanced Calculus Kernel..."}

    params   = data.get("parameters", {})
    raw_expr = params.get("expression", data.get("raw_query", ""))
    expr_str = clean_math_string(raw_expr)
    prob_type = data.get("problem_type", "").lower()

    if not expr_str:
        yield {"type": "final",
               "answer": "Error: no calculus expression found to analyse."}
        return

    try:
        vars_detected = detect_variables(expr_str) or ["x"]
        yield {"type": "step",
               "content": f"Variables identified: {', '.join(vars_detected)}"}

        symbols      = {v: sp.Symbol(v) for v in vars_detected}
        vars_list    = [symbols[v] for v in vars_detected]
        primary_var  = vars_list[0]
        expr_lower   = expr_str.lower()

        steps = []

        # ------------------------------------------------------------------ #
        # 1. Taylor / Maclaurin Series
        # ------------------------------------------------------------------ #
        if "taylor" in expr_lower or "maclaurin" in expr_lower or "series" in prob_type:
            yield {"type": "step",
                   "content": "Computing Taylor Series Expansion..."}

            clean_expr, point, order = _parse_series_args(expr_str)
            expr   = safe_sympify(clean_expr, symbols=symbols)
            result = sp.series(expr, primary_var, point, order)
            result_no_O = result.removeO()

            steps = [
                "### Taylor Series Expansion",
                f"**Function:** $f({primary_var}) = {sp.latex(expr)}$",
                f"**Expansion point:** $x_0 = {point}$  |  **Order:** $n = {order}$",
                "",
                f"**Series:**\n{_latex_block(result)}",
                f"**Polynomial (no Big-O):**\n{_latex_block(result_no_O)}",
            ]

        # ------------------------------------------------------------------ #
        # 2. Gradient
        # ------------------------------------------------------------------ #
        elif _keyword_in("gradient", expr_lower, prob_type) or _keyword_in("grad", expr_lower, prob_type):
            yield {"type": "step", "content": "Computing Gradient Vector (∇f)..."}

            clean_expr = clean_math_string(
                expr_str.replace("gradient", "").replace("grad", "").replace("nabla", "")
            )
            expr = safe_sympify(clean_expr, symbols=symbols)
            grad = [sp.diff(expr, v) for v in vars_list]

            grad_latex = (
                "\\begin{bmatrix} "
                + " \\\\ ".join(sp.latex(g) for g in grad)
                + " \\end{bmatrix}"
            )
            steps = [
                "### Gradient Vector Field",
                f"**Scalar function:** $f({', '.join(vars_detected)}) = {sp.latex(expr)}$",
                f"**Result:** $\\nabla f = {grad_latex}$",
                "",
                "**Component partials:**",
                *[f"- $\\partial f/\\partial {sp.latex(v)} = {sp.latex(g)}$"
                  for v, g in zip(vars_list, grad)],
            ]

        # ------------------------------------------------------------------ #
        # 3. ODEs  — check before "integrate" so "y'' + y = 0" is routed here
        # ------------------------------------------------------------------ #
        elif ("ode" in expr_lower or "differential equation" in expr_lower
              or ("=" in expr_str and any(c in expr_str for c in ("y''", "y'", "dy")))):
            yield {"type": "step", "content": "Solving Ordinary Differential Equation..."}
            steps = await _solve_ode(expr_str)

        # ------------------------------------------------------------------ #
        # 4. Fourier Series
        # ------------------------------------------------------------------ #
        elif "fourier" in expr_lower:
            yield {"type": "step", "content": "Computing Fourier Series expansion..."}
            steps = _solve_fourier(expr_str, symbols)

        # ------------------------------------------------------------------ #
        # 5. Multiple / definite integration
        # ------------------------------------------------------------------ #
        elif ("∫" in expr_str or "integrate" in expr_lower
              or "integral" in prob_type or "integral" in expr_lower):
            yield {"type": "step", "content": "Performing Integration..."}
            steps = _solve_integration(expr_str, symbols, vars_list)

        # ------------------------------------------------------------------ #
        # 6. Partial / ordinary derivatives
        # ------------------------------------------------------------------ #
        elif any(kw in prob_type or kw in expr_lower
                 for kw in ("derivative", "partial", "diff", "d/")):
            yield {"type": "step", "content": "Computing Derivatives..."}
            steps = _solve_derivatives(expr_str, symbols, vars_list, primary_var)

        # ------------------------------------------------------------------ #
        # 7. Laplace transform
        # ------------------------------------------------------------------ #
        elif "laplace" in expr_lower or "laplace" in prob_type:
            yield {"type": "step", "content": "Computing Laplace Transform..."}
            steps = _solve_laplace(expr_str, symbols, primary_var)

        # ------------------------------------------------------------------ #
        # 8. Auto-detect: derivative + integral
        # ------------------------------------------------------------------ #
        else:
            yield {"type": "step",
                   "content": "Auto-detecting expression structure..."}
            expr      = safe_sympify(expr_str, symbols=symbols)
            diff_res  = sp.diff(expr, primary_var)
            int_res   = sp.integrate(expr, primary_var)
            simplified = sp.simplify(expr)

            steps = [
                "### Calculus Analysis",
                f"**Expression:** ${sp.latex(expr)}$",
                f"**Simplified:** ${sp.latex(simplified)}$",
                f"**Derivative** ($d/d{primary_var}$): ${sp.latex(diff_res)}$",
                f"**Antiderivative** ($\\int \\cdot d{primary_var}$): ${sp.latex(int_res)} + C$",
            ]

        yield {"type": "final", "answer": "\n\n".join(steps)}

    except Exception as exc:
        yield {"type": "final", "answer": f"Calculus Engine Error: {exc}"}


# ---------------------------------------------------------------------------
# Sub-routines
# ---------------------------------------------------------------------------

def _parse_series_args(expr_str):
    """Extract (clean_expr, expansion_point, order) from a Taylor/series string."""
    text    = expr_str.lower()
    point   = 0
    order   = 6
    clean   = expr_str

    # Remove keywords
    for kw in ("taylor", "maclaurin", "series", "expansion", "of"):
        clean = clean.lower().replace(kw, " ")
    clean = clean.strip()

    if "around" in clean:
        parts  = clean.split("around", 1)
        clean  = parts[0].strip()
        try:
            point = float(parts[1].split()[0])
        except (IndexError, ValueError):
            pass

    if "order" in clean:
        parts = clean.split("order", 1)
        clean = parts[0].strip()
        try:
            order = int(parts[1].split()[0])
        except (IndexError, ValueError):
            pass

    return clean or "x", point, order


def _solve_derivatives(expr_str, symbols, vars_list, primary_var):
    """Return step-list for partial/total derivatives."""
    clean = clean_math_string(
        expr_str.replace("partial", "").replace("derivative of", "").replace("diff", "")
    )
    expr    = safe_sympify(clean, symbols=symbols)
    results = []
    for v in vars_list:
        d1 = sp.diff(expr, v)
        d2 = sp.diff(d1, v)
        results.append(
            f"- $\\partial f/\\partial {sp.latex(v)} = {sp.latex(d1)}$  "
            f"  (2nd: ${sp.latex(d2)}$)"
        )

    return [
        "### Partial Differentiation",
        f"**Function:** $f = {sp.latex(expr)}$",
        "**Results:**",
        *results,
    ]


def _solve_integration(expr_str, symbols, vars_list):
    """Return step-list for integration."""
    # Count integration symbols / keywords for multi-fold
    count_int = expr_str.count("∫")
    count_dbl = expr_str.lower().count("double")
    count_tri = expr_str.lower().count("triple")
    dim = count_int or (count_dbl * 2) or (count_tri * 3) or 1

    clean = clean_math_string(
        expr_str
        .replace("∫", "")
        .replace("triple", "")
        .replace("double", "")
        .replace("integral of", "")
        .replace("integrate", "")
    )
    expr   = safe_sympify(clean, symbols=symbols)
    result = expr
    vars_used = []
    for i in range(min(dim, len(vars_list))):
        result    = sp.integrate(result, vars_list[i])
        vars_used.append(vars_list[i])

    var_str = "".join(f" d{sp.latex(v)}" for v in vars_used)
    return [
        f"### {dim}-fold Integration",
        f"**Integrand:** ${sp.latex(expr)}$",
        f"**Primitive (∫{var_str}):** ${sp.latex(result)} + C$",
        f"**Simplified:** ${sp.latex(sp.simplify(result))} + C$",
    ]


async def _solve_ode(expr_str):
    """Return step-list for a linear ODE."""
    t = sp.Symbol("t")
    y = sp.Function("y")(t)

    # Support y(x) notation too
    x = sp.Symbol("x")

    try:
        parts   = expr_str.split("=", 1)
        lhs_str = parts[0].strip()
        rhs_str = parts[1].strip() if len(parts) > 1 else "0"

        # Normalise derivative notation
        for notation, replacement in (
            ("y'''", "Derivative(y(t),t,3)"),
            ("y''",  "Derivative(y(t),t,2)"),
            ("y'",   "Derivative(y(t),t)"),
            ("dy/dt","Derivative(y(t),t)"),
        ):
            lhs_str = lhs_str.replace(notation, replacement)
            rhs_str = rhs_str.replace(notation, replacement)

        lhs_sym = safe_sympify(lhs_str, symbols={"y": y, "t": t})
        rhs_sym = safe_sympify(rhs_str, symbols={"t": t})
        ode_eq  = sp.Eq(lhs_sym, rhs_sym)
        sol     = sp.dsolve(ode_eq, y)

        return [
            "### Ordinary Differential Equation",
            f"**Equation:** {_latex_block(ode_eq)}",
            f"**General Solution:** {_latex_block(sol)}",
        ]

    except Exception as exc:
        return [
            "### ODE Solver",
            f"Could not parse or solve the ODE: {exc}",
            "Expected format: `y'' + 2*y' + y = sin(t)`",
        ]


def _solve_fourier(expr_str, symbols):
    """Return step-list for a Fourier series."""
    x = sp.Symbol("x")
    local_symbols = {**symbols, "x": x}

    clean = clean_math_string(
        expr_str.lower()
        .replace("fourier", "")
        .replace("series", "")
        .replace("of", "")
        .strip()
    )
    expr = safe_sympify(clean, symbols=local_symbols)

    # Detect period from params if provided, else assume 2π
    fs = sp.fourier_series(expr, (x, -sp.pi, sp.pi))

    return [
        "### Fourier Series",
        f"**Function:** $f(x) = {sp.latex(expr)}$  on $[-\\pi, \\pi]$",
        "**First 5 non-zero terms:**",
        _latex_block(fs.truncate(5)),
    ]


def _solve_laplace(expr_str, symbols, primary_var):
    """Return step-list for a Laplace transform."""
    t = sp.Symbol("t", positive=True)
    s = sp.Symbol("s")
    local_sym = {**symbols, "t": t, "s": s}

    clean = clean_math_string(
        expr_str.lower()
        .replace("laplace", "")
        .replace("transform", "")
        .replace("of", "")
        .strip()
    )
    expr   = safe_sympify(clean, symbols=local_sym)
    result = sp.laplace_transform(expr, t, s, noconds=True)

    return [
        "### Laplace Transform",
        f"**Function:** $f(t) = {sp.latex(expr)}$",
        f"**Result:** $\\mathcal{{L}}\\{{f(t)\\}} = {sp.latex(result)}$",
]
