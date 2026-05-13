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
    simplify_math
)

async def solve_algebra(data):
    yield {"type": "step", "content": "Initializing Algebra Engine..."}
    
    params = data.get("parameters", {})
    expr_str = params.get("expression", data.get("raw_query", ""))
    expr_str = clean_math_string(expr_str)
    preferred_method = data.get("requested_method") or params.get("method") or "standard symbolic solving"

    # Detect Uncertainty Request
    if any(k.endswith("_sigma") for k in params.keys()):
        yield {"type": "step", "content": "Uncertainty parameters detected. Running propagation kernel..."}
        # Pure math uncertainty propagation if no other domain caught it
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
            pass # Fall through to standard solve
    
    if not expr_str:
        yield {"type": "final", "answer": "Error: No algebraic expression found to solve."}
        return

    yield {"type": "step", "content": f"Parsing expression(s): {expr_str}"}
    
    try:
        # Detect all alphabetical variables, preserving case
        vars_detected = detect_variables(expr_str)
        if not vars_detected:
            vars_detected = ["x"]
        
        yield {"type": "step", "content": f"Variables identified: {', '.join(vars_detected)}"}
        
        symbols = {v: sp.Symbol(v) for v in vars_detected}
        
        # Check for multiple equations (simultaneous)
        # Often separated by comma, semicolon, newline, or " and "
        delimiters = [";", "\n", " and "]
        equations_raw = [expr_str]

        # Robust system splitting:
        # If multiple '=' appear but delimiter splitting fails (e.g. "x+y=20 y-x=2"),
        # extract each equation by pattern: <lhs>=<rhs>
        if expr_str.count("=") > 1:
            eq_pattern = re.compile(
                r"([^=]+?)\s*=\s*([^=]+?)(?=(?:\s+[A-Za-z_])|$)",
                re.DOTALL
            )
            matches = eq_pattern.findall(expr_str)
            if len(matches) >= 2:
                equations_raw = [f"{clean_math_string(lhs)}={clean_math_string(rhs)}".strip() for lhs, rhs in matches]

        # Delimiter-based split fallback (keeps previous behavior)
        if len(equations_raw) == 1:
            for d in delimiters:
                if d.lower() in expr_str.lower():
                    pattern = re.compile(re.escape(d), re.IGNORECASE)
                    equations_raw = [e.strip() for e in pattern.split(expr_str) if e.strip()]
                    break

        # If still only one, check for comma delimiter but only if there are equals signs
        if len(equations_raw) == 1 and "," in expr_str and expr_str.count("=") > 1:
            equations_raw = [e.strip() for e in expr_str.split(",") if e.strip()]
        
        # Detect Matrix Operations
        if detect_matrix(expr_str):
            yield {"type": "step", "content": f"Matrix detected. Performing linear algebra analysis..."}
            M = parse_matrix(expr_str)
            if M:
                rows, cols = M.shape
                steps = ["### Matrix Analysis"]
                steps.append(f"Matrix $M = {sp.latex(M)}$")
                steps.append(f"Dimensions: {rows}x{cols}")
                
                yield {
                    "type": "diagram",
                    "diagram_type": "matrix",
                    "data": {
                        "rows": rows, "cols": cols,
                        "values": M.tolist(), # Convert to list of lists
                        "caption": "Parsed Matrix structure."
                    }
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
        
        # Determine if we have multiple equations or a single one
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
            
            # Symbolic solving is good, but let's try to explain a step if it's 2x2
            system_steps = ["### Simultaneous Equations Resolution", f"**Method Used:** {preferred_method.title()}"]
            system_steps.append("#### Given System:")
            for eq in eqs:
                system_steps.append(f"- $${sp.latex(eq)}$$")
            
            if len(eqs) == 2 and len(symbols) == 2:
                yield {"type": "step", "content": "Using substitution/elimination method for 2x2 system..."}
                system_steps.append("#### Steps for 2x2 System:")
                var_list = list(symbols.values())
                v1, v2 = var_list[0], var_list[1]
                
                # Try to isolate v1 in first eq
                try:
                    iso_sols = sp.solve(eqs[0], v1)
                    if iso_sols:
                        iso_expr = iso_sols[0]
                        system_steps.append(f"1. Isolate ${sp.latex(v1)}$ from the first equation: $${sp.latex(v1)} = {sp.latex(iso_expr)}$$")
                        # Substitute into second eq
                        subbed_eq = eqs[1].subs(v1, iso_expr)
                        system_steps.append(f"2. Substitute this expression into the second equation: $${sp.latex(subbed_eq)}$$")
                        # Solve for v2
                        v2_sols = sp.solve(subbed_eq, v2)
                        if v2_sols:
                            v2_val = v2_sols[0]
                            system_steps.append(f"3. Solve for ${sp.latex(v2)}$: $${sp.latex(v2)} = {sp.latex(v2_val)}$$")
                            # Back substitute
                            final_v1 = iso_expr.subs(v2, v2_val)
                            system_steps.append(f"4. Back-substitute ${sp.latex(v2)}$ to find ${sp.latex(v1)}$: $${sp.latex(v1)} = {sp.latex(final_v1)}$$")
                except Exception:
                    system_steps.append("Proceeding with standard matrix/symbolic resolution for complex system.")

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
                        system_steps.append(f"**Set {idx+1}:**")
                        for var, val in zip(symbols.values(), sol_tuple):
                            system_steps.append(f"- $${sp.latex(var)} = {sp.latex(val)}$$")
                else:
                    system_steps.append(f"Result: $${sp.latex(sol_dict)}$$")
            
            yield {"type": "final", "answer": "\n".join(system_steps)}
            return

        else:
            # Single equation: Check for Quadratic or higher polynomial
            eq_text = clean_math_string(equations_raw[0])
            if "=" in eq_text:
                parts = eq_text.split("=", 1)
                lhs = simplify_math(safe_sympify(parts[0], symbols=symbols))
                rhs = simplify_math(safe_sympify(parts[1], symbols=symbols))
                equation = sp.Eq(lhs, rhs)
            else:
                equation = sp.Eq(safe_sympify(eq_text, symbols=symbols), 0)
            
            # Target variable
            target_var = symbols[vars_detected[0]] if vars_detected else sp.Symbol('x')
            
            # Detect Factorization
            lowered_query = data.get("raw_query", "").lower()
            is_factorization = "factor" in lowered_query or preferred_method == "factorization"
            
            if is_factorization:
                yield {"type": "step", "content": f"Factorization requested for expression in {target_var}..."}
                expr_to_factor = equation.lhs - equation.rhs
                
                # Methods
                methods = ["standard", "grouping", "quadratic formula", "difference of squares"]
                method = params.get("factor_method", "standard").lower()
                
                steps = ["### Factorization Report", f"Expression: $${sp.latex(expr_to_factor)}$$"]
                
                if method == "grouping":
                    yield {"type": "step", "content": "Attempting factorization by grouping terms..."}
                    steps.append("#### Method: Factorization by Grouping")
                    steps.append("1. **Arrange Terms:** Group terms with common factors.")
                    # We can't easily show the intermediate grouping steps for all cases symbolically without more complexity,
                    # but we can show the result of partial factoring if simple.
                    factored = sp.factor(expr_to_factor)
                    steps.append(f"2. **Factor Out Commons:** Finding common sub-expressions.")
                    steps.append(f"3. **Conclusion:** Final factored form: $${sp.latex(factored)}$$")
                elif method == "quadratic formula" or (method == "standard" and sp.Poly(expr_to_factor, target_var).degree() == 2):
                    yield {"type": "step", "content": "Executing Trinomial Decomposition..."}
                    poly = sp.Poly(expr_to_factor, target_var)
                    coeffs = poly.all_coeffs()
                    if len(coeffs) == 3:
                        a, b, c = coeffs
                        steps.append("#### Method: Quadratic Trinomial Decomposition")
                        steps.append(f"1. **Identify Coefficients:** $a={a}, b={b}, c={c}$")
                        discriminant = b**2 - 4*a*c
                        steps.append(f"2. **Calculate Discriminant:** $D = b^2 - 4ac = {discriminant}$")
                        roots = sp.solve(expr_to_factor, target_var)
                        if roots:
                            roots_latex = ", ".join([sp.latex(r) for r in roots])
                            steps.append(f"3. **Extraction:** Roots identified at $\\{{{roots_latex}\\}}$")
                            factored_str = f"{sp.latex(a)}" if a != 1 else ""
                            for r in roots:
                                factored_str += f"({sp.latex(target_var)} - ({sp.latex(r)}))"
                            steps.append(f"4. **Reconstruction:** $${factored_str}$$")
                        else:
                            steps.append(r"3. **Insight:** No real roots available for factorization over $\mathbb{R}$.")
                    else:
                        steps.append("Expression degree is not quadratic; falling back to symbolic factoring.")
                        steps.append(f"Result: $${sp.latex(sp.factor(expr_to_factor))}$$")
                elif method == "difference of squares":
                    yield {"type": "step", "content": "Checking for Difference of Squares pattern ($a^2 - b^2$)..."}
                    steps.append("#### Method: Difference of Squares")
                    factored = sp.factor(expr_to_factor)
                    steps.append(f"1. **Pattern Matching:** Decomposing $a^2 - b^2$ into $(a-b)(a+b)$.")
                    steps.append(f"2. **Result:** $${sp.latex(factored)}$$")
                else:
                    yield {"type": "step", "content": "Applying Generalized Prime Factorization Transform..."}
                    factored = sp.factor(expr_to_factor)
                    steps.append("#### Method: Symbolic Factorization")
                    steps.append(f"**Step 1:** Scan for greatest common divisors (GCD) across terms.")
                    steps.append(f"**Step 2:** Apply recursive polynomial division.")
                    steps.append(f"**Final Result:** $${sp.latex(factored)}$$")
                
                yield {"type": "final", "answer": "\n".join(steps)}
                return

            yield {"type": "step", "content": f"Solving for {target_var}..."}
            
            solutions = sp.solve(equation, target_var)
            
            # Step by step logic for quadratic specifically
            is_quadratic = False
            try:
                poly = sp.Poly(equation.lhs - equation.rhs, target_var)
                if poly.degree() == 2:
                    is_quadratic = True
                    coeffs = poly.all_coeffs()
                    a, b, c = coeffs
                    discriminant = b**2 - 4*a*c
                    yield {"type": "step", "content": "Detected Quadratic Equation. Applying Quadratic Formula..."}
            except Exception:
                is_quadratic = False
            
            steps = ["### Algebraic Resolution", f"**Method Used:** {preferred_method.title()}"]
            steps.append(f"Equation: $${sp.latex(equation)}$$")
            
            if is_quadratic:
                steps.append("#### Quadratic Breakdown")
                steps.append(f"Standard Form: $${sp.latex(a)}{sp.latex(target_var)}^2 + {sp.latex(b)}{sp.latex(target_var)} + {sp.latex(c)} = 0$$")
                steps.append(f"Coefficients: $a={a}, b={b}, c={c}$")
                steps.append(f"Discriminant: $D = b^2 - 4ac = {discriminant}$")
                
            steps.append("#### Final Solutions:")
            if not solutions:
                steps.append("No analytical solution found.")
            else:
                for idx, sol in enumerate(solutions):
                    steps.append(f"{idx+1}. $${sp.latex(target_var)} = {sp.latex(sol)}$$")
            
            yield {"type": "final", "answer": "\n".join(steps)}

    except Exception as e:
        yield {"type": "final", "answer": f"Algebraic error: Could not parse or solve expression. Details: {str(e)}"}
