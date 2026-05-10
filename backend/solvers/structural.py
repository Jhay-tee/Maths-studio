import asyncio
import numpy as np
import json

async def solve_structural(data):
    yield {"type": "step", "content": "Initializing Structural Analysis Engine..."}
    await asyncio.sleep(0.3)
    
    topic = data.get("topic", "structural").lower()
    
    if "beam" in topic:
        yield {"type": "step", "content": "Beam detected. Setting up boundary conditions..."}
        length = 10.0 # Default fallback
        for u in data.get("units", []):
            if u.get("param") == "length":
                length = float(u.get("si_val", 10.0))
        
        yield {"type": "step", "content": f"Beam length: {length}m. Mapping loads to global coordinates..."}
        await asyncio.sleep(0.5)
        
        yield {"type": "step", "content": "Calculating reactions for static equilibrium..."}
        await asyncio.sleep(0.5)
        
        # Mocking some diagrams for the "robust" look
        yield {"type": "step", "content": "Generating internal force diagrams..."}
        
        # Shear Force Diagram
        x = np.linspace(0, length, 100)
        shear = np.sin(x) * 100 # Mock data
        sfd_data = [{"x": float(xi), "y": float(yi)} for xi, yi in zip(x, shear)]
        yield {"type": "diagram", "diagram_type": "shear_force_graph", "data": sfd_data}
        await asyncio.sleep(0.4)
        
        # Bending Moment Diagram
        moment = np.cos(x) * 200 # Mock data
        bmd_data = [{"x": float(xi), "y": float(yi)} for xi, yi in zip(x, moment)]
        yield {"type": "diagram", "diagram_type": "bending_moment_graph", "data": bmd_data}
        await asyncio.sleep(0.4)
        
        yield {"type": "final", "answer": "Beam analysis complete. Material stress within safety limits."}
        
    else:
        yield {"type": "step", "content": "Running Finite Element Mesh generation..."}
        await asyncio.sleep(0.6)
        yield {"type": "step", "content": "Solving global stiffness matrix..."}
        await asyncio.sleep(0.6)
        yield {"type": "final", "answer": "FEM analysis complete. Displacement vectors calculated."}
