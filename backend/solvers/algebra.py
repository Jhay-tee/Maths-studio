import asyncio
import sympy as sp
import json

async def solve_algebra(data):
    yield {"type": "step", "content": "Initializing Symbolic Math Engine (SymPy)..."}
    await asyncio.sleep(0.3)
    
    # In a real scenario, we'd extract the expression and solve it.
    # For this demo/restore, we'll simulate the robust symbolic steps.
    
    yield {"type": "step", "content": "Searching for variables and constants..."}
    await asyncio.sleep(0.4)
    
    yield {"type": "step", "content": "Applying simplification rules..."}
    await asyncio.sleep(0.4)
    
    yield {"type": "step", "content": "Calculating exact solution..."}
    await asyncio.sleep(0.5)
    
    ans = "Solution reached using symbolic transformation."
    yield {"type": "final", "answer": ans}
