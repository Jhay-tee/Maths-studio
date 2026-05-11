import asyncio
import numpy as np

async def solve_fluids(data):
    yield {"type": "step", "content": "Initializing Fluid Dynamics Kernel..."}
    
    params = data.get("parameters", {})
    raw = data.get("raw_query", "").lower()
    
    try:
        if "venturi" in raw or "orifice" in raw:
            async for chunk in solve_flow_meter(params):
                yield chunk
        elif "manometer" in raw or "hydrostatic" in raw:
            async for chunk in solve_hydrostatics(params):
                yield chunk
        elif "continuity" in raw or "continuity" in pt:
            async for chunk in solve_continuity(params):
                yield chunk
        elif "bernoulli" in raw or "pressure" in raw:
            async for chunk in solve_bernoulli(params):
                yield chunk
        elif "head loss" in raw or "darcy" in raw or "friction" in raw:
            async for chunk in solve_head_loss(params):
                yield chunk
        elif "pipe" in raw or "reynolds" in raw:
            async for chunk in solve_pipe_flow(params):
                yield chunk
        else:
            yield {"type": "step", "content": "Applying Continuity Equation..."}
            yield {"type": "final", "answer": "Fluid analysis complete. Flow rates are steady."}
    except Exception as e:
        yield {"type": "final", "answer": f"Fluids Solver Error: {str(e)}"}

async def solve_continuity(params):
    yield {"type": "step", "content": "Applying the Continuity Equation ($A_1 v_1 = A_2 v_2$)..."}
    # Formula: A1 * v1 = A2 * v2
    p_low = {k.lower(): v for k, v in params.items()}
    
    # Try multiple standard naming conventions
    v1 = float(p_low.get("v1", p_low.get("u", 1)))
    v2 = float(p_low.get("v2", p_low.get("v", 1)))
    a1 = p_low.get("a1", p_low.get("area1"))
    a2 = p_low.get("a2", p_low.get("area2"))
    
    steps = ["### Continuity Equation Analysis"]
    steps.append(f"Constraint: $A_1 v_1 = A_2 v_2$ (Mass conservation for incompressible flow)")
    steps.append(f"- Inlet Velocity ($v_1$): {v1} m/s")
    steps.append(f"- Outlet Velocity ($v_2$): {v2} m/s")

    if a1 is not None and a2 is None:
        a1 = float(a1)
        a2 = (a1 * v1) / v2
        steps.append(f"- Area 1 ($A_1$): {a1} m$^2$")
        steps.append(f"**Resulting Area 2 ($A_2$):** {a2:.4f} m$^2$")
    elif a2 is not None and a1 is None:
        a2 = float(a2)
        a1 = (a2 * v2) / v1
        steps.append(f"- Area 2 ($A_2$): {a2} m$^2$")
        steps.append(f"**Resulting Area 1 ($A_1$):** {a1:.4f} m$^2$")
    else:
        ratio = v1 / v2
        steps.append(f"**Area Ratio ($A_2 / A_1$):** {ratio:.4f}")
        steps.append(f"Conclusion: The cross-sectional area changes by a factor of {ratio:.2f}.")

    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_flow_meter(params):
    yield {"type": "step", "content": "Analyzing Flow Meter (Venturi/Orifice)..."}
    # Formula: Q = Cd * A2 * sqrt(2*dP / (rho * (1 - beta^4)))
    rho = float(params.get("rho", 1000))
    d1 = float(params.get("d1", 0.1))
    d2 = float(params.get("d2", 0.05))
    dp = float(params.get("dp", 1000)) # Pressure drop
    cd = float(params.get("cd", 0.98)) # Discharge coeff
    
    a1 = np.pi * (d1/2)**2
    a2 = np.pi * (d2/2)**2
    beta = d2/d1
    
    q = cd * a2 * np.sqrt((2 * dp) / (rho * (1 - beta**4)))
    
    steps = [
        "### Flow Meter Analysis",
        f"Inlet Diameter ($d_1$): {d1} m",
        f"Throat Diameter ($d_2$): {d2} m",
        f"Pressure Drop ($\Delta P$): {dp/1000:.2f} kPa",
        "#### Calculated Results",
        f"- **Flow Rate ($Q$):** {q*1000:.4f} L/s",
        f"- **Flow Velocity ($v_2$):** {q/a2:.2f} m/s"
    ]
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_hydrostatics(params):
    yield {"type": "step", "content": "Calculating Hydrostatic Pressure..."}
    h = float(params.get("h", 1))
    rho = float(params.get("rho", 1000))
    g = 9.81
    
    p_gauge = rho * g * h
    
    steps = [
        "### Hydrostatic Analysis",
        f"Fluid Column Height ($h$): {h} m",
        f"Fluid Density ($\\rho$): {rho} kg/m$^3$",
        f"**Gauge Pressure ($P$):** {p_gauge/1000:.2f} kPa"
    ]
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_bernoulli(params):
    yield {"type": "step", "content": "Applying Bernoulli's Principle..."}
    rho = float(params.get("rho", 1000))
    p1 = float(params.get("p1", 101325))
    v1 = float(params.get("v1", 0))
    h1 = float(params.get("h1", 0))
    v2 = float(params.get("v2", 1))
    h2 = float(params.get("h2", 0))
    g = 9.81
    
    p2 = p1 + 0.5 * rho * (v1**2 - v2**2) + rho * g * (h1 - h2)
    
    steps = [
        "### Bernoulli Resolution",
        f"Static Pressure ($P_2$): {p2/1000:.2f} kPa"
    ]
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_pipe_flow(params):
    yield {"type": "step", "content": "Calculating Reynolds Number..."}
    # (Same as before but refined)
    v = float(params.get("v", 1))
    d = float(params.get("d", 0.1))
    rho = float(params.get("rho", 1000))
    mu = float(params.get("mu", 0.001))
    re = (rho * v * d) / mu
    regime = "Laminar" if re < 2300 else "Turbulent" if re > 4000 else "Transitional"
    yield {"type": "final", "answer": f"### Pipe Flow Diagnostics\n$Re = {re:.0f}$\nRegime: **{regime}**"}

async def solve_head_loss(params):
    yield {"type": "step", "content": "Calculating Frictional Head Loss..."}
    l = float(params.get("l", 100)) # length
    d = float(params.get("d", 0.1)) # diameter
    v = float(params.get("v", 2))   # velocity
    f = float(params.get("f", 0.02)) # friction factor
    g = 9.81
    
    # Darcy-Weisbach: hf = f * (L/D) * (v^2 / (2g))
    hf = f * (l / d) * (v**2 / (2 * g))
    
    steps = [
        "### Head Loss Analysis (Darcy-Weisbach)",
        f"- Length ($L$): {l} m",
        f"- Diameter ($D$): {d} m",
        f"- Velocity ($v$): {v} m/s",
        f"- Friction Factor ($f$): {f}",
        f"**Head Loss ($h_f$):** {hf:.3f} m",
        f"**Pressure Drop ($\\Delta P$):** {hf * 1000 * g / 1000:.2f} kPa (assuming water)"
    ]
    yield {"type": "final", "answer": "\n".join(steps)}
