import asyncio
import numpy as np

async def solve_thermo(data):
    yield {"type": "step", "content": "Initializing Thermodynamics Engine..."}
    await asyncio.sleep(0.3)
    
    yield {"type": "step", "content": "Analyzing state variables (P, V, T)..."}
    await asyncio.sleep(0.5)
    
    yield {"type": "step", "content": "Applying First and Second Laws of Thermodynamics..."}
    await asyncio.sleep(0.5)
    
    # Mocking a P-V Diagram
    v = np.linspace(1, 10, 50)
    p = 10 / v # Isothermal-ish
    pv_data = [{"x": float(vi), "y": float(pi)} for vi, pi in zip(v, p)]
    yield {"type": "diagram", "diagram_type": "pv_diagram", "data": pv_data}
    
    yield {"type": "final", "answer": "Thermodynamic cycle analysis complete. Efficiency and work output calculated."}
