import numpy as np
from solvers.constants import WATER_DENSITY, WATER_VISCOSITY, G
from solvers.utils import normalize_params, validate_physical_params


def series_points(x_values, y_values):
    return [{"x": float(x), "y": float(y)} for x, y in zip(x_values, y_values)]


async def solve_fluids(data):
    yield {"type": "step", "content": "Initializing Fluid Dynamics Kernel..."}

    params = normalize_params(data.get("parameters", {}))
    
    # Physical validation
    is_valid, err = validate_physical_params(params)
    if not is_valid:
        yield {"type": "error", "message": err}
        return
        
    raw = data.get("raw_query", "").lower()
    pt = data.get("problem_type", "").lower()
    
    # Display variables used
    used_vars = [k for k in params.keys() if params[k] is not None]
    if used_vars:
        yield {"type": "step", "content": f"Boundary conditions detected: {', '.join(used_vars)}"}

    try:
        if any(keyword in pt or keyword in raw for keyword in ["venturi", "orifice", "flow_meter"]):
            async for chunk in solve_flow_meter(params):
                yield chunk
        elif any(keyword in pt or keyword in raw for keyword in ["manometer", "hydrostatic", "hydrostatics", "pressure at the bottom", "bubble", "vegetable oil", "hole at the bottom"]):
            async for chunk in solve_hydrostatics(params, raw):
                yield chunk
        elif "continuity" in pt or "continuity" in raw:
            async for chunk in solve_continuity(params):
                yield chunk
        elif any(keyword in pt or keyword in raw for keyword in ["bernoulli", "pressure"]):
            async for chunk in solve_bernoulli(params):
                yield chunk
        elif any(keyword in pt or keyword in raw for keyword in ["head loss", "darcy", "friction"]):
            async for chunk in solve_head_loss(params):
                yield chunk
        elif any(keyword in pt or keyword in raw for keyword in ["pipe", "reynolds"]):
            async for chunk in solve_pipe_flow(params):
                yield chunk
        elif any(keyword in pt or keyword in raw for keyword in ["pump", "power"]):
            async for chunk in solve_pump_power(params):
                yield chunk
        else:
            yield {"type": "final", "answer": "Fluid problem detected, but I need a clearer type such as continuity, Bernoulli, hydrostatics, pipe flow, head loss, venturi, or pump power."}
    except Exception as e:
        yield {"type": "final", "answer": f"Fluids Solver Error: {str(e)}"}


async def solve_continuity(params):
    yield {"type": "step", "content": "Applying continuity and cross-sectional area relations..."}

    v1 = params.get("v1", params.get("u"))
    v2 = params.get("v2", params.get("v"))
    a1 = params.get("a1", params.get("area1"))
    a2 = params.get("a2", params.get("area2"))
    d1 = params.get("d1", params.get("D1", params.get("diameter1")))
    d2 = params.get("d2", params.get("D2", params.get("diameter2")))

    v1 = None if v1 in (None, "") else float(v1)
    v2 = None if v2 in (None, "") else float(v2)
    a1 = None if a1 in (None, "") else float(a1)
    a2 = None if a2 in (None, "") else float(a2)
    d1 = None if d1 in (None, "") else float(d1)
    d2 = None if d2 in (None, "") else float(d2)

    if a1 is None and d1 is not None:
        a1 = np.pi * (d1 ** 2) / 4
    if a2 is None and d2 is not None:
        a2 = np.pi * (d2 ** 2) / 4

    if None not in (a1, v1, a2) and v2 is None and a2 != 0:
        v2 = a1 * v1 / a2
    elif None not in (a2, v2, a1) and v1 is None and a1 != 0:
        v1 = a2 * v2 / a1
    elif None not in (a1, v1, v2) and a2 is None and v2 != 0:
        a2 = a1 * v1 / v2
    elif None not in (a2, v2, v1) and a1 is None and v1 != 0:
        a1 = a2 * v2 / v1

    if None in (a1, a2, v1, v2):
        yield {"type": "final", "answer": "Continuity needs three known quantities among $A_1$, $A_2$, $v_1$, and $v_2$ (diameters can be used instead of areas)."}
        return

    positions = np.array([1, 2])
    velocities = np.array([v1, v2])
    yield {"type": "diagram", "diagram_type": "pressure_curve", "data": series_points(positions, velocities)}

    steps = [
        "### Continuity Equation Analysis",
        f"- Area 1: {a1:.6f} m^2",
        f"- Area 2: {a2:.6f} m^2",
        f"- Velocity 1: {v1:.4f} m/s",
        f"- Velocity 2: {v2:.4f} m/s",
        f"- Flow rate: $Q = A_1 v_1 = {a1 * v1:.6f}$ m^3/s",
    ]
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_hydrostatics(params, raw_query=""):
    yield {"type": "step", "content": "Computing hydrostatic pressure variation with depth..."}
    h = float(params.get("h", params.get("depth", 1)))
    rho = float(params.get("rho", WATER_DENSITY))
    g = 9.81

    p_gauge = rho * g * h
    
    # Uncertainty Analysis
    uncertainties = {k.replace("_sigma", ""): v for k, v in params.items() if k.endswith("_sigma")}
    p_sigma = 0
    if uncertainties:
        from solvers.utils import propagate_uncertainty
        expr = "rho * g * h"
        p_eval = {"rho": rho, "g": g, "h": h}
        p_sigma = propagate_uncertainty(expr, p_eval, uncertainties)

    depths = np.linspace(0, max(h, 1e-6), 60)
    pressures = rho * g * depths / 1000
    yield {"type": "diagram", "diagram_type": "pressure_curve", "data": series_points(depths, pressures)}

    steps = [
        "### Hydrostatic Analysis",
        f"- **Depth ($h$):** {h:.4f} m",
        f"- **Density ($\\rho$):** {rho:.2f} kg/m³",
        f"- **Gauge pressure:** {p_gauge:.2f} Pa ({p_gauge / 1000:.4f} kPa)",
    ]
    if p_sigma > 0:
        from solvers.utils import append_uncertainty_to_final
        steps = append_uncertainty_to_final(steps, "Gauge Pressure", p_gauge, p_sigma, "Pa")
    if raw_query:
        if "add more water" in raw_query:
            steps.append("- Adding more water increases the pressure because pressure grows with liquid height.")
        if "vegetable oil" in raw_query:
            steps.append("- For the same height, vegetable oil gives a lower pressure because its density is lower than water.")
        if "bubble" in raw_query:
            steps.append("- The air bubble expands as it rises because the surrounding pressure decreases toward the surface.")
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_bernoulli(params):
    yield {"type": "step", "content": "Applying Bernoulli head balance between two sections..."}
    rho = float(params.get("rho", WATER_DENSITY))
    p1 = float(params.get("p1", 101325))
    v1 = float(params.get("v1", 0))
    h1 = float(params.get("h1", 0))
    p2 = params.get("p2")
    v2 = params.get("v2")
    h2 = float(params.get("h2", 0))
    g = 9.81

    p2 = None if p2 in (None, "") else float(p2)
    v2 = None if v2 in (None, "") else float(v2)

    total_head_1 = p1 / (rho * g) + (v1 ** 2) / (2 * g) + h1
    
    if p2 is None and v2 is not None:
        p2 = rho * g * (total_head_1 - (v2 ** 2) / (2 * g) - h2)
    elif v2 is None and p2 is not None:
        v2_head = max(0.0, 2 * g * (total_head_1 - p2 / (rho * g) - h2))
        v2 = np.sqrt(v2_head)
    
    ans = [
        "### Bernoulli Energy Analysis",
        f"- **Section 1 Total Head:** {total_head_1:.4f} m",
        f"- **Section 2 Pressure:** {p2:.2f} Pa" if p2 else "",
        f"- **Section 2 Velocity:** {v2:.4f} m/s" if v2 else "",
        "- **Note:** Ideal flow assumed (Energy Grade Line = Hydraulic Grade Line)."
    ]
    yield {"type": "final", "answer": "\n".join(filter(None, ans))}

async def solve_flow_meter(params):
    yield {"type": "step", "content": "Evaluating flow meter characteristics (Venturi/Orifice)..."}
    rho = float(params.get("rho", WATER_DENSITY))
    d1 = float(params.get("d1", 0.1))
    d2 = float(params.get("d2", 0.05))
    dp = float(params.get("dp", 1000))
    Cd = float(params.get("cd", 0.98)) # Discharge coefficient

    A1 = np.pi * (d1**2) / 4
    A2 = np.pi * (d2**2) / 4
    
    Q = Cd * A2 * np.sqrt((2 * dp) / (rho * (1 - (A2/A1)**2)))
    v1 = Q / A1
    v2 = Q / A2

    ans = [
        "### Flow Meter Performance",
        f"- **Flow Rate ($Q$):** {Q:.6f} m³/s",
        f"- **Throat Velocity ($v_2$):** {v2:.4f} m/s",
        f"- **Inlet Velocity ($v_1$):** {v1:.4f} m/s",
        f"- **Area Ratio:** {(A2/A1):.3f}"
    ]
    yield {"type": "final", "answer": "\n".join(ans)}


async def solve_pipe_flow(params):
    yield {"type": "step", "content": "Determining flow regime and velocity profiles..."}
    v = float(params.get("v", params.get("velocity", 1.0)))
    D = float(params.get("D", params.get("d", 0.1)))
    rho = float(params.get("rho", WATER_DENSITY))
    mu = float(params.get("mu", WATER_VISCOSITY))

    Re = (rho * v * D) / mu if mu else 0
    regime = "Laminar" if Re < 2300 else "Turbulent" if Re > 4000 else "Transitional"
    
    # Velocity Profile (Parabolic for laminar, power law for turbulent)
    r = np.linspace(-D/2, D/2, 50)
    if Re < 2300:
        v_profile = v * 2 * (1 - (r/(D/2))**2)
    else:
        v_profile = v * (8/7) * (1 - np.abs(r/(D/2)))**(1/7) # 1/7th power law approx
        
    yield {
        "type": "diagram",
        "diagram_type": "velocity_profile",
        "data": [{"r": float(ri), "v": float(vi)} for ri, vi in zip(r, v_profile)]
    }

    ans = [
        "### Pipe Flow Diagnostics",
        f"- **Reynolds Number ($Re$):** {Re:.2f}",
        f"- **Flow Regime:** **{regime}**",
        "- **Profile Description:** " + ("Parabolic (Laminar)" if Re < 2300 else "Logarithmic/Power-law (Turbulent)")
    ]
    yield {"type": "final", "answer": "\n".join(ans)}

async def solve_head_loss(params):
    yield {"type": "step", "content": "Calculating energy dissipation via Darcy-Weisbach relations..."}
    L = float(params.get("L", 100))
    D = float(params.get("D", 0.1))
    v = float(params.get("v", 2))
    f = float(params.get("f", 0.02)) # Darcy friction factor
    g = 9.81
    
    hf = f * (L/D) * (v**2 / (2*g))
    dp = hf * WATER_DENSITY * g
    
    ans = [
        "### Major Head Loss Report",
        f"- **Darcy Friction Factor ($f$):** {f}",
        f"- **Head Loss ($h_f$):** {hf:.4f} m",
        f"- **Pressure Drop ($\\Delta P$):** {dp/1000:.2f} kPa",
        f"- **Loss Gradient:** {hf/L:.4f} m/m"
    ]
    yield {"type": "final", "answer": "\n".join(ans)}


async def solve_pump_power(params):
    yield {"type": "step", "content": "Computing hydraulic power and pump demand..."}
    rho = float(params.get("rho", WATER_DENSITY))
    g = float(params.get("g", G))
    q = float(params.get("Q", params.get("q", 0.01)))
    head = float(params.get("H", params.get("head", 10)))
    eta = float(params.get("eta", params.get("efficiency", 0.75)))

    hydraulic_power = rho * g * q * head
    shaft_power = hydraulic_power / eta if eta else hydraulic_power

    yield {"type": "final", "answer": f"### Pump Power Analysis\n- Flow rate: {q:.6f} m^3/s\n- Pump head: {head:.4f} m\n- Hydraulic power: {hydraulic_power:.2f} W\n- Shaft power: {shaft_power:.2f} W"}
