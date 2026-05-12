import asyncio
import sympy as sp
import re
from solvers.utils import safe_sympify, clean_math_string

async def solve_algebra(data):
    yield {"type": "step", "content": "Initializing Algebra Engine..."}
    
    params = data.get("parameters", {})
    expr_str = params.get("expression", data.get("raw_query", ""))
    expr_str = clean_math_string(expr_str)
    preferred_method = data.get("requested_method") or params.get("method") or "standard symbolic solving"
    
    if not expr_str:
        yield {"type": "final", "answer": "Error: No algebraic expression found to solve."}
        return

    yield {"type": "step", "content": f"Parsing expression(s): {expr_str}"}
    
    try:
        # Detect all alphabetical variables, preserving case
        all_potential = set(re.findall(r'[a-zA-Z]', expr_str))
        # Exclude common single-letter constants if they are alone (e, i, d)
        # But for algebra, we usually want to keep them.
        vars_to_use = sorted(list(all_potential))
        if not vars_to_use:
            vars_to_use = ["x"]
        
        symbols = {v: sp.Symbol(v) for v in vars_to_use}
        
        # Check for multiple equations (simultaneous)
        # Often separated by comma, semicolon, newline, or " and "
        delimiters = [";", "\n", " and "]
        equations_raw = [expr_str]
        for d in delimiters:
            if d.lower() in expr_str.lower():
                # Correctly split while ignoring case for " and "
                pattern = re.compile(re.escape(d), re.IGNORECASE)
                equations_raw = [e.strip() for e in pattern.split(expr_str) if e.strip()]
                break
        
        # If still only one, check for comma delimiter but only if there are equals signs
        if len(equations_raw) == 1 and "," in expr_str and expr_str.count("=") > 1:
            equations_raw = [e.strip() for e in expr_str.split(",") if e.strip()]
        
        # Detect Matrix Operations
        if "[" in expr_str and "]" in expr_str:
            yield {"type": "step", "content": f"Detected matrix structure. Using {preferred_method} for linear algebra analysis..."}
            # Simple matrix parsing from string like [[1,2],[3,4]]
            import ast
            try:
                # Clean string for ast.literal_eval
                matrix_raw = expr_str.strip()
                if "=" in matrix_raw: matrix_raw = matrix_raw.split("=")[-1].strip()
                
                # Try to find the matrix within the string if it's not the whole string
                start = matrix_raw.find("[")
                end = matrix_raw.rfind("]") + 1
                matrix_data = ast.literal_eval(matrix_raw[start:end])
                
                M = sp.Matrix(matrix_data)
                rows, cols = M.shape
                
                steps = ["### Linear Algebra Analysis", f"**Method Used:** {preferred_method.title()}"]
                steps.append(f"Matrix $M = {sp.latex(M)}$")
                steps.append(f"Dimensions: {rows}x{cols}")
                yield {
                    "type": "diagram",
                    "diagram_type": "matrix",
                    "data": {
                        "rows": rows,
                        "cols": cols,
                        "values": matrix_data,
                        "caption": "Matrix interpreted from the user input.",
                    },
                }
                
                if rows == cols:
                    yield {"type": "step", "content": "Computing Determinant and Inverse..."}
                    det = M.det()
                    steps.append(f"- **Determinant:** $|M| = {sp.latex(det)}$")
                    
                    if det != 0:
                        inv = M.inv()
                        steps.append(f"- **Inverse:** $M^{{-1}} = {sp.latex(inv)}$")
                    else:
                        steps.append("- **Inverse:** Matrix is singular (determinant is zero).")
                    
                    if rows <= 3: # Limit eigenvalues for speed
                        yield {"type": "step", "content": "Calculating Eigenvalues..."}
                        eigs = M.eigenvals()
                        steps.append("**Eigenvalues:**")
                        for val, mult in eigs.items():
                            steps.append(f"- $\\lambda = {sp.latex(val)}$ (multiplicity: {mult})")
                
                yield {"type": "final", "answer": "\n".join(steps)}
                return
            except Exception as me:
                yield {"type": "step", "content": f"Matrix parsing failed: {str(me)}. Falling back to expression solving."}
        
        # Determine if we have multiple equations or a single one
        if len(equations_raw) > 1:
            yield {"type": "step", "content": f"Detected {len(equations_raw)} simultaneous equations."}
            eqs = []
            for eq_text in equations_raw:
                eq_text = clean_math_string(eq_text)
                if "=" in eq_text:
                    parts = eq_text.split("=", 1)
                    lhs = safe_sympify(parts[0], symbols=symbols)
                    rhs = safe_sympify(parts[1], symbols=symbols)
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

        else:
            # Single equation: Check for Quadratic or higher polynomial
            eq_text = clean_math_string(equations_raw[0])
            if "=" in eq_text:
                parts = eq_text.split("=", 1)
                lhs = safe_sympify(parts[0], symbols=symbols)
                rhs = safe_sympify(parts[1], symbols=symbols)
                equation = sp.Eq(lhs, rhs)
            else:
                equation = sp.Eq(safe_sympify(eq_text, symbols=symbols), 0)
            
            # Target variable
            target_var = symbols[vars_to_use[0]] if vars_to_use else sp.Symbol('x')
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
