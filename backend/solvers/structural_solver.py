import asyncio
import json
import math

async def solve_structural(data):
    """
    Simulates a structural analysis solver (e.g., Truss or Frame).
    """
    yield {"type": "step", "content": "Initializing structural analysis engine..."}
    await asyncio.sleep(0.5)
    
    nodes = data.get('nodes', 4)
    members = data.get('members', 5)
    
    yield {"type": "step", "content": f"Building stiffness matrix for {nodes} nodes and {members} members..."}
    await asyncio.sleep(0.6)
    
    yield {"type": "step", "content": "Applying boundary conditions and nodal loads..."}
    await asyncio.sleep(0.4)
    
    yield {"type": "step", "content": "Solving system equilibrium equations (KU = P)..."}
    await asyncio.sleep(0.8)
    
    # Mock data for axial force diagram
    axial_data = []
    for i in range(11):
        x = i * 1.0
        # Simulated axial force distribution
        y = 50 * math.cos(i * 0.3) 
        axial_data.append({"x": x, "y": y})
        
    yield {"type": "diagram", "diagram_type": "axial_force_graph", "data": axial_data}
    yield {"type": "step", "content": "Axial Force Diagram (AFD) generated."}
    
    yield {"type": "final", "answer": f"Structural Analysis Complete. Safety Factor: 1.65. Max Displacement: 12.4mm."}
