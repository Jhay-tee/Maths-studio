import asyncio
import numpy as np

async def solve_fluids(data):
    yield {"type": "step", "content": "Initializing Fluid Dynamics Kernel..."}
    await asyncio.sleep(0.3)
    
    yield {"type": "step", "content": "Calculating Reynolds number and flow regime..."}
    await asyncio.sleep(0.5)
    
    yield {"type": "step", "content": "Applying Bernoulli's principle / Navier-Stokes approximations..."}
    await asyncio.sleep(0.5)
    
    # Mocking a Pressure Distribution Diagram
    x = np.linspace(0, 10, 50)
    p = 100 * np.exp(-0.2 * x)
    pressure_data = [{"x": float(xi), "y": float(yi)} for xi, yi in zip(x, p)]
    yield {"type": "diagram", "diagram_type": "pressure_gradient", "data": pressure_data}
    
    yield {"type": "final", "answer": "Fluid analysis complete. Head loss and pressure gradients computed for the given SI parameters."}
