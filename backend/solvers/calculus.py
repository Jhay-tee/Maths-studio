import asyncio
import sympy as sp

async def solve_calculus(data):
    yield {"type": "step", "content": "Initializing Advanced Calculus Kernel..."}
    
    params = data.get("parameters", {})
    expr_str = params.get("expression", data.get("raw_query", ""))
    prob_type = data.get("problem_type", "").lower()
    
    if not expr_str:
        yield {"type": "final", "answer": "Error: No calculus expression found to analyze."}
        return

    try:
        # Detect all alphabetical variables, preserving case
        import re
        all_potential = set(re.findall(r'[a-zA-Z]', expr_str))
        # For calculus, we often use x, t, or user defined vars
        vars_to_use = sorted(list(all_potential))
        if not vars_to_use:
            vars_to_use = ["x"]
        
        symbols = {v: sp.Symbol(v) for v in vars_to_use}
        vars_list = [symbols[v] for v in vars_to_use]
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

            expr = sp.sympify(clean_expr, locals=symbols)
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
            clean_expr = expr_str.replace("gradient", "").replace("grad", "").replace("nabla", "").strip()
            expr = sp.sympify(clean_expr, locals=symbols)
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
            clean_expr = expr_str.replace("∫", "").replace("triple", "").replace("double", "").replace("integral of", "").replace("integrate", "").strip()
            expr = sp.sympify(clean_expr, locals=symbols)
            
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
            clean_expr = expr_str.replace("partial", "").replace("derivative of", "").strip()
            expr = sp.sympify(clean_expr, locals=symbols)
            
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
                lhs_str, rhs_str = expr_str.split("=")
                lhs = sp.sympify(lhs_str.replace("y''", "y.diff(t, t)").replace("y'", "y.diff(t)"), locals={'y': y, 't': t})
                rhs = sp.sympify(rhs_str, locals={'t': t})
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
            expr = sp.sympify(expr_str.lower().replace("fourier", "").replace("series", "").replace("of", "").split("from")[0].strip())
            fs = sp.fourier_series(expr, (x, -sp.pi, sp.pi))
            steps.extend([
                "### Fourier Analysis",
                f"**Function:** $f(x) = {sp.latex(expr)}$",
                "**First 3 Terms:**",
                f"$${sp.latex(fs.truncate(3))}$$"
            ])

        else:
            yield {"type": "step", "content": "Auto-detecting multivariable structure..."}
            expr = sp.sympify(expr_str, locals=symbols)
            diff_res = sp.diff(expr, primary_var)
            int_res = sp.integrate(expr, primary_var)
            
            steps.extend([
                f"**Expression:** $${sp.latex(expr)}$$",
                f"**Derivative ($\partial/\partial {sp.latex(primary_var)}$):** $${sp.latex(diff_res)}$$",
                f"**Antiderivative ($\int \cdot d{sp.latex(primary_var)}$):** $${sp.latex(int_res)} + C$$"
            ])

        yield {"type": "final", "answer": "\n\n".join(steps)}

    except Exception as e:
        yield {"type": "final", "answer": f"Calculus Engine Error: {str(e)}"}
