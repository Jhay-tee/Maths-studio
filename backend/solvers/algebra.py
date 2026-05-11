import asyncio
import sympy as sp

async def solve_algebra(data):
    yield {"type": "step", "content": "Initializing Algebra Engine..."}
    
    params = data.get("parameters", {})
    expr_str = params.get("expression", data.get("raw_query", ""))
    
    if not expr_str:
        yield {"type": "final", "answer": "Error: No algebraic expression found to solve."}
        return

    yield {"type": "step", "content": f"Parsing expression(s): {expr_str}"}
    
    try:
        # Check for multiple equations (simultaneous)
        # Often separated by comma, semicolon, or newline
        delimiters = [",", ";", "\n"]
        equations_raw = [expr_str]
        for d in delimiters:
            if d in expr_str:
                equations_raw = [e.strip() for e in expr_str.split(d) if e.strip()]
                break
        
        # Detect Matrix Operations
        if "[" in expr_str and "]" in expr_str:
            yield {"type": "step", "content": "Detected Matrix structure. Performing Linear Algebra analysis..."}
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
                
                steps = ["### Linear Algebra Analysis"]
                steps.append(f"Matrix $M = {sp.latex(M)}$")
                steps.append(f"Dimensions: {rows}x{cols}")
                
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
            yield {"type": "step", "content": f"Detected {len(equations_raw)} simultaneous equations."}
            eqs = []
            for eq_text in equations_raw:
                if "=" in eq_text:
                    lhs_str, rhs_str = eq_text.split("=")
                    lhs = sp.sympify(lhs_str.strip(), locals=symbols)
                    rhs = sp.sympify(rhs_str.strip(), locals=symbols)
                    eqs.append(sp.Eq(lhs, rhs))
                else:
                    eqs.append(sp.Eq(sp.sympify(eq_text.strip(), locals=symbols), 0))
            
            yield {"type": "step", "content": "Solving system of equations..."}
            sol_dict = sp.solve(eqs, list(symbols.values()))
            
            steps = ["### Simultaneous Equations Resolution"]
            steps.append("#### Given System:")
            for eq in eqs:
                steps.append(f"- $${sp.latex(eq)}$$")
            
            steps.append("#### Solutions:")
            if not sol_dict:
                steps.append("No solution found for the given system.")
            elif isinstance(sol_dict, dict):
                for var, val in sol_dict.items():
                    steps.append(f"- $${sp.latex(var)} = {sp.latex(val)}$$")
            elif isinstance(sol_dict, list):
                if len(sol_dict) > 0 and isinstance(sol_dict[0], tuple):
                    for idx, sol_tuple in enumerate(sol_dict):
                        steps.append(f"**Set {idx+1}:**")
                        for var, val in zip(symbols.values(), sol_tuple):
                            steps.append(f"- $${sp.latex(var)} = {sp.latex(val)}$$")
                else:
                    steps.append(f"Result: $${sp.latex(sol_dict)}$$")
            
            yield {"type": "final", "answer": "\n".join(steps)}

        else:
            # Single equation: Check for Quadratic or higher polynomial
            eq_text = equations_raw[0]
            if "=" in eq_text:
                lhs_str, rhs_str = eq_text.split("=")
                lhs = sp.sympify(lhs_str.strip(), locals=symbols)
                rhs = sp.sympify(rhs_str.strip(), locals=symbols)
                equation = sp.Eq(lhs, rhs)
            else:
                equation = sp.Eq(sp.sympify(eq_text.strip(), locals=symbols), 0)
            
            # Target variable
            target_var = symbols[potential_vars[0]] if potential_vars else sp.Symbol('x')
            yield {"type": "step", "content": f"Solving for {target_var}..."}
            
            solutions = sp.solve(equation, target_var)
            
            # Step by step logic for quadratic specifically
            is_quadratic = False
            poly = sp.Poly(equation.lhs - equation.rhs, target_var)
            if poly.degree() == 2:
                is_quadratic = True
                coeffs = poly.all_coeffs()
                a, b, c = coeffs
                discriminant = b**2 - 4*a*c
                yield {"type": "step", "content": "Detected Quadratic Equation. Applying Quadratic Formula..."}
            
            steps = ["### Algebraic Resolution"]
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
