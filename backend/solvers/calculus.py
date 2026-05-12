import asyncio
import sympy as sp
from solvers.utils import safe_sympify, clean_math_string, simplify_math, detect_variables

async def solve_calculus(data):
    yield {"type": "step", "content": "Initializing Advanced Calculus Kernel..."}
    
    params = data.get("parameters", {})
    expr_str = params.get("expression", data.get("raw_query", ""))
    expr_str = clean_math_string(expr_str)
    prob_type = data.get("problem_type", "").lower()
    
    if not expr_str:
        yield {"type": "final", "answer": "Error: No calculus expression found to analyze."}
        return

    try:
        # Detect variables
        vars_detected = detect_variables(expr_str)
        if not vars_detected:
            vars_detected = ["x"]
        
        yield {"type": "step", "content": f"Variables identified: {', '.join(vars_detected)}"}
        
        symbols = {v: sp.Symbol(v) for v in vars_detected}
        vars_list = [symbols[v] for v in vars_detected]
        primary_var = vars_list[0]

        steps = [f"### Advanced Calculus Analysis"]
        
        # 1. Taylor Series
        if "taylor" in expr_str.lower() or "series" in prob_type:
            yield {"type": "step", "content": "Computing Taylor Series Expansion..."}
            # Try to extract point and order
            # Default: around 0, order 6
            clean_expr = expr_str.lower().replace("taylor", "").replace("series", "").replace("expansion", "").strip()
            # Basic parsing for "around X" or "order Y"
            point = 0
            order = 6
            if "around" in clean_expr:
                parts = clean_expr.split("around")
                clean_expr = parts[0].strip()
                try:
                    point = float(parts[1].split()[0])
                except: pass
            if "order" in clean_expr:
                parts = clean_expr.split("order")
                clean_expr = parts[0].strip()
                try:
                    order = int(parts[1].split()[0])
                except: pass

            expr = safe_sympify(clean_expr, symbols=symbols)
            result = sp.series(expr, primary_var, point, order)
            
            steps.extend([
                f"**Operation:** Taylor Series Expansion",
                f"**Function:** $f({primary_var}) = {sp.latex(expr)}$",
                f"**Center Point:** $x_0 = {point}$",
                f"**Order:** $n = {order}$",
                f"**Expansion:** $${sp.latex(result)}$$"
            ])

        # 2. Gradient Calculation
        elif any(kw in expr_str.lower() or kw in prob_type for kw in ["gradient", "grad", "nabla"]):
            yield {"type": "step", "content": "Computing Gradient Vector (∇f)..."}
            clean_expr = clean_math_string(expr_str.replace("gradient", "").replace("grad", "").replace("nabla", ""))
            expr = safe_sympify(clean_expr, symbols=symbols)
            grad = [sp.diff(expr, v) for v in vars_list]
            
            grad_latex = "\\begin{bmatrix} " + " \\\\ ".join([sp.latex(g) for g in grad]) + " \\end{bmatrix}"
            steps.extend([
                f"**Operation:** Gradient Vector Field",
                f"**Scalar Function:** $f({', '.join(vars_to_use)}) = {sp.latex(expr)}$",
                f"**Result:** $\\nabla f = {grad_latex}$"
            ])

        # 3. Multiple Integration
        elif "integral" in prob_type or "∫" in expr_str or "integrate" in expr_str.lower():
            yield {"type": "step", "content": "Performing Multiple Integration..."}
            dim = expr_str.count("∫") or expr_str.lower().count("double") * 2 or expr_str.lower().count("triple") * 3 or 1
            clean_expr = clean_math_string(expr_str.replace("∫", "").replace("triple", "").replace("double", "").replace("integral of", "").replace("integrate", ""))
            expr = safe_sympify(clean_expr, symbols=symbols)
            
            result = expr
            for i in range(min(dim, len(vars_list))):
                result = sp.integrate(result, vars_list[i])
            
            steps.extend([
                f"**Operation:** {dim}-fold Integration",
                f"**Integrand:** $${sp.latex(expr)}$$",
                f"**Primitive:** $${sp.latex(result)} + C$$"
            ])

        # 4. Partial Derivatives
        elif any(kw in prob_type or kw in expr_str.lower() for kw in ["derivative", "partial", "d/"]):
            yield {"type": "step", "content": "Computing Partial Derivatives..."}
            clean_expr = clean_math_string(expr_str.replace("partial", "").replace("derivative of", ""))
            expr = safe_sympify(clean_expr, symbols=symbols)
            
            results = []
            for v in vars_list:
                results.append(f"$\\frac{{\\partial f}}{{\\partial {sp.latex(v)}}} = {sp.latex(sp.diff(expr, v))}$")
            
            steps.extend([
                f"**Operation:** Partial Differentiation",
                f"**Function:** $f = {sp.latex(expr)}$",
                "**Results:**",
                "\n".join([f"- {r}" for r in results])
            ])

        # 5. Laplace Transform... (already added)

        # 6. Differential Equations (ODEs)
        elif "ode" in expr_str.lower() or "diff" in expr_str.lower() and "=" in expr_str:
            yield {"type": "step", "content": "Solving Differential Equation..."}
            # Handle equation like y'' + 2y' + y = 0
            # Requires symbolic function y(t)
            t = sp.Symbol('t')
            y = sp.Function('y')(t)
            
            # Very basic parser for 2nd/1st order linear
            # expr_str format assumed: "y'' + 2*y' + y = sin(t)"
            try:
                parts = expr_str.split("=", 1)
                lhs_str = parts[0]
                rhs_str = parts[1] if len(parts) > 1 else "0"
                lhs = safe_sympify(lhs_str.replace("y''", "y.diff(t, t)").replace("y'", "y.diff(t)"), symbols={'y': y, 't': t})
                rhs = safe_sympify(rhs_str, symbols={'t': t})
                eq = sp.Eq(lhs, rhs)
                sol = sp.dsolve(eq, y)
                steps.extend([
                    "### Differential Equation Solution",
                    f"**Equation:** $${sp.latex(eq)}$$",
                    f"**General Solution:** $${sp.latex(sol)}$$"
                ])
            except Exception as de:
                steps.append(f"ODE Solver failed: {str(de)}. Ensure format like `y'' + y = 0`.")

        # 7. Fourier Series
        elif "fourier" in expr_str.lower():
            yield {"type": "step", "content": "Computing Fourier Series expansion..."}
            # Format: Fourier series of x^2 from -pi to pi
            x = sp.Symbol('x')
            clean_expr = clean_math_string(expr_str.lower().replace("fourier", "").replace("series", "").replace("of", ""))
            expr = safe_sympify(clean_expr)
            fs = sp.fourier_series(expr, (x, -sp.pi, sp.pi))
            steps.extend([
                "### Fourier Analysis",
                f"**Function:** $f(x) = {sp.latex(expr)}$",
                "**First 3 Terms:**",
                f"$${sp.latex(fs.truncate(3))}$$"
            ])

        else:
            yield {"type": "step", "content": "Auto-detecting multivariable structure..."}
            expr = safe_sympify(expr_str, symbols=symbols)
            diff_res = sp.diff(expr, primary_var)
            int_res = sp.integrate(expr, primary_var)
            
            steps.extend([
                f"**Expression:** $${sp.latex(expr)}$$",
                f"**Derivative ($\\partial/\\partial {sp.latex(primary_var)}$):** $${sp.latex(diff_res)}$$",
                f"**Antiderivative ($\\int \\cdot d{sp.latex(primary_var)}$):** $${sp.latex(int_res)} + C$$"
            ])

        yield {"type": "final", "answer": "\n\n".join(steps)}

    except Exception as e:
        yield {"type": "final", "answer": f"Calculus Engine Error: {str(e)}"}
