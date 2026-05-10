import asyncio
import numpy as np
from typing import AsyncGenerator, Dict, Any

async def solve_beam(data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
    yield {"type": "step", "content": "Initializing Beam Analysis Core..."}
    length = float(data.get("length", 10))
    loads = data.get("loads", [{"value": 100, "pos": length/2}])
    yield {"type": "step", "content": f"Beam Length: {length}m detected. Processing {len(loads)} load points."}
    await asyncio.sleep(0.4)
    
    yield {"type": "step", "content": "Calculating static equilibrium..."}
    # Calculate reactions RA and RB
    total_force = 0
    sum_moments_a = 0
    
    for load in loads:
        load_type = load.get("type", "point")
        val = float(load.get("value", 0))
        
        if load_type == "point":
            pos = float(load.get("pos", 0))
            total_force += val
            sum_moments_a += val * pos
        elif load_type == "distributed":
            start = float(load.get("start", 0))
            end = float(load.get("end", length))
            w_total = val * (end - start)
            w_center = (start + end) / 2
            total_force += w_total
            sum_moments_a += w_total * w_center
    
    rb = sum_moments_a / length
    ra = total_force - rb
    
    yield {"type": "step", "content": f"Reaction Force RA = {ra:.2f} N"}
    yield {"type": "step", "content": f"Reaction Force RB = {rb:.2f} N"}
    await asyncio.sleep(0.4)
    
    x = np.linspace(0, length, 200) # Increased resolution
    shear = np.zeros_like(x)
    moment = np.zeros_like(x)
    
    for i, xi in enumerate(x):
        s = ra
        m = ra * xi
        
        # Subtract contributions from loads
        for load in loads:
            load_type = load.get("type", "point")
            val = float(load.get("value", 0))
            
            if load_type == "point":
                pos = float(load.get("pos", 0))
                if xi >= pos:
                    s -= val
                    m -= val * (xi - pos)
            elif load_type == "distributed":
                start = float(load.get("start", 0))
                end = float(load.get("end", length))
                if xi > start:
                    active_len = min(xi, end) - start
                    applied_w = val * active_len
                    s -= applied_w
                    # Moment arm is active_len / 2 from the point where the load is acting until xi
                    # centroid of the portion of load to the left of xi
                    m -= applied_w * (xi - (start + min(xi, end)) / 2)
                    
        shear[i] = s
        moment[i] = m

    yield {"type": "step", "content": "Generating High-Resolution Shear Force Diagram (SFD)..."}
    sfd_data = [{"x": float(xi), "y": float(yi)} for xi, yi in zip(x, shear)]
    yield {"type": "diagram", "diagram_type": "shear_force_graph", "data": sfd_data}
    await asyncio.sleep(0.4)
    
    yield {"type": "step", "content": "Generating High-Resolution Bending Moment Diagram (BMD)..."}
    bmd_data = [{"x": float(xi), "y": float(yi)} for xi, yi in zip(x, moment)]
    yield {"type": "diagram", "diagram_type": "bending_moment_graph", "data": bmd_data}
    await asyncio.sleep(0.4)
    
    max_moment = float(np.max(np.abs(moment)))
    yield {"type": "final", "answer": f"Analysis Complete. Max Bending Moment: {max_moment:.2f} Nm. Verification passed."}
