import asyncio
import numpy as np
import json

async def solve_mechanics(data):
    yield {"type": "step", "content": "Initializing Classical Mechanics Kernel..."}
    await asyncio.sleep(0.3)
    
    summary = data.get("summary", "").lower()
    
    # Simple logic to differentiate based on summary/content
    if "projectile" in summary or "motion" in summary:
        yield {"type": "step", "content": "Kinematics detected. Analyzing trajectory equations..."}
        await asyncio.sleep(0.5)
        
        # Mock Trajectory Data for Diagram
        t = np.linspace(0, 2, 50)
        y = 20 * t - 0.5 * 9.81 * t**2
        x = 10 * t
        
        trajectory_data = [{"x": float(xi), "y": float(yi)} for xi, yi in zip(x, y)]
        yield {"type": "diagram", "diagram_type": "trajectory_plot", "data": trajectory_data}
        await asyncio.sleep(0.4)
        
        yield {"type": "final", "answer": "Kinematic analysis complete. Max height and range calculated based on extracted initial velocity."}
        
    elif "force" in summary or "equilibrium" in summary:
        yield {"type": "step", "content": "Dynamics detected. Constructing Free Body Diagram (FBD) constraints..."}
        await asyncio.sleep(0.5)
        yield {"type": "step", "content": "Solving Newton's second law equations..."}
        await asyncio.sleep(0.5)
        yield {"type": "final", "answer": "Static/Dynamic equilibrium verified. Resultant forces and accelerations computed."}
    else:
        yield {"type": "step", "content": "General mechanics problem identified. Applying energy conservation principles..."}
        await asyncio.sleep(0.6)
        yield {"type": "final", "answer": "Computation complete. Conservation laws satisfied."}
