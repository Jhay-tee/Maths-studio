import asyncio
import sympy
from typing import AsyncGenerator, Dict, Any

async def solve_algebra(data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
    yield {"type": "step", "content": "Initializing Symbolic Engine (SymPy)..."}
    await asyncio.sleep(0.3)
    
    # Extract expression or equation
    expr_str = data.get("expression", data.get("problem", ""))
    if not expr_str:
        yield {"type": "final", "answer": "Error: No expression provided to solver."}
        return

    yield {"type": "step", "content": f"Parsing input: {expr_str}"}
    
    try:
        # Simple heuristic to handle equations with '='
        if '=' in expr_str:
            left, right = expr_str.split('=')
            lhs = sympy.simplify(left.strip())
            rhs = sympy.simplify(right.strip())
            eq = sympy.Eq(lhs, rhs)
            
            yield {"type": "step", "content": "Detecting variables..."}
            vars = eq.free_symbols
            
            if not vars:
                res = lhs == rhs
                yield {"type": "final", "answer": f"The equation is {res}"}
            else:
                target_var = list(vars)[0]
                yield {"type": "step", "content": f"Solving for {target_var}..."}
                solution = sympy.solve(eq, target_var)
                yield {"type": "final", "answer": f"{target_var} = {solution}"}
        else:
            # Try to simplify expression
            expr = sympy.simplify(expr_str)
            yield {"type": "step", "content": "Simplifying expression..."}
            yield {"type": "final", "answer": f"Result: {expr}"}
            
    except Exception as e:
        yield {"type": "final", "answer": f"Solver Error: {str(e)}. Attempting numerical approximation..."}
