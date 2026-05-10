import asyncio
import sympy as sp

async def solve_calculus(params):
    yield {"type": "step", "content": "Initializing Symbolic Calculus Engine..."}

    expr_str = params.get("expression")
    operation = params.get("operation")  # derivative | integral | limit
    variable = params.get("variable", "x")

    x = sp.Symbol(variable)

    yield {"type": "step", "content": "Parsing symbolic expression..."}

    expr = sp.sympify(expr_str)

    await asyncio.sleep(0.2)

    # ---------------- DERIVATIVE ----------------
    if operation == "derivative":
        yield {"type": "step", "content": "Computing derivative using symbolic rules..."}
        result = sp.diff(expr, x)

    # ---------------- INTEGRAL ----------------
    elif operation == "integral":
        yield {"type": "step", "content": "Computing symbolic integral..."}
        result = sp.integrate(expr, x)

    # ---------------- LIMIT ----------------
    elif operation == "limit":
        point = params.get("point")
        direction = params.get("direction", "+")
        yield {"type": "step", "content": "Evaluating limit..."}
        result = sp.limit(expr, x, point, dir=direction)

    else:
        yield {"type": "final", "error": "Invalid calculus operation"}
        return

    await asyncio.sleep(0.2)

    yield {
        "type": "final",
        "answer": str(result)
    }
