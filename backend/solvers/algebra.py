import asyncio
import sympy as sp

async def solve_algebra(data):
    yield {"type": "step", "content": "Parsing algebraic expression..."}

    expr_str = data.get("expression", "")
    x = sp.Symbol("x")

    # convert string → sympy equation
    expr = sp.Eq(*map(sp.sympify, expr_str.split("=")))

    yield {"type": "step", "content": "Converting to symbolic form..."}

    await asyncio.sleep(0.2)

    yield {"type": "step", "content": "Solving equation..."}

    solution = sp.solve(expr, x)

    await asyncio.sleep(0.2)

    yield {"type": "final", "answer": solution}
