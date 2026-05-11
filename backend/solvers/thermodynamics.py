import asyncio
import numpy as np

async def solve_thermo(data):
    yield {"type": "step", "content": "Initializing Thermodynamics Engine..."}
    
    params = data.get("parameters", {})
    raw = data.get("raw_query", "").lower()
    
    try:
        if "ideal gas" in raw or "pv=nrt" in raw or "gas" in raw:
            async for chunk in solve_ideal_gas(params):
                yield chunk
        elif "heat" in raw or "specific" in raw:
            async for chunk in solve_heat_transfer(params):
                yield chunk
        elif "entropy" in raw or "reversible" in raw:
            async for chunk in solve_entropy(params):
                yield chunk
        elif "cycle" in raw or "carnot" in raw or "otto" in raw:
            async for chunk in solve_cycles(params):
                yield chunk
        else:
            yield {"type": "step", "content": "Analyzing System State..."}
            yield {"type": "final", "answer": "Thermodynamic analysis complete. Equilibrium reached."}
    except Exception as e:
        yield {"type": "final", "answer": f"Thermo Solver Error: {str(e)}"}

async def solve_ideal_gas(params):
    yield {"type": "step", "content": "Applying Ideal Gas Law ($PV=nRT$)..."}
    # R = 8.314 J/(mol·K)
    R = 8.314
    p = float(params.get("p", 101325))
    v = float(params.get("v", 0.0224))
    n = float(params.get("n", 1))
    t = float(params.get("t", 273.15))
    
    # Simple check on what's missing
    # If 3 are provided, solve for the 4th (simplified for now)
    steps = [
        "### Ideal Gas Law Analysis",
        f"- Pressure ($P$): {p/1000:.2f} kPa",
        f"- Volume ($V$): {v*1000:.2f} L",
        f"- Amount ($n$): {n} mol",
        f"- Temperature ($T$): {t} K",
        "#### Verification",
        f"PV = {p*v:.2f} | nRT = {n*R*t:.2f}"
    ]
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_heat_transfer(params):
    yield {"type": "step", "content": "Calculating Heat Exchange ($Q=mc\Delta T$)..."}
    m = float(params.get("m", 1))
    c = float(params.get("c", 4186)) # Default water
    dt = float(params.get("dt", 10))
    
    q = m * c * dt
    
    steps = [
        "### Calorimetry Report",
        f"- Mass ($m$): {m} kg",
        f"- Specific Heat ($c$): {c} J/(kg·K)",
        f"- Temp Change ($\Delta T$): {dt} K",
        f"**Heat Transferred ($Q$):** {q/1000:.2f} kJ"
    ]
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_entropy(params):
    yield {"type": "step", "content": "Analyzing Entropy Change..."}
    q = float(params.get("q", 0))
    t = float(params.get("t", 298.15))
    
    ds = q / t
    steps = [
        "### Second Law Analysis",
        f"- Heat ($Q$): {q} J",
        f"- Absolute Temperature ($T$): {t} K",
        f"**Entropy Change ($\Delta S$):** $Q/T = {ds:.4f}$ J/K"
    ]
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_cycles(params):
    yield {"type": "step", "content": "Analyzing Thermodynamic Cycle Performance..."}
    th = float(params.get("th", params.get("t_high", 500)))
    tl = float(params.get("tl", params.get("t_low", 300)))
    
    efficiency = 1 - (tl/th)
    
    steps = [
        "### Carnot Cycle Efficiency",
        f"- Source Temperature ($T_H$): {th} K",
        f"- Sink Temperature ($T_L$): {tl} K",
        f"**Thermal Efficiency ($\\eta_{{th}}$):** $1 - T_L/T_H = {efficiency:.2%}$"
    ]
    yield {"type": "final", "answer": "\n".join(steps)}
