import numpy as np
from solvers.constants import WATER_DENSITY, WATER_VISCOSITY, G


def series_points(x_values, y_values):
    return [{"x": float(x), "y": float(y)} for x, y in zip(x_values, y_values)]


async def solve_fluids(data):
    yield {"type": "step", "content": "Initializing Fluid Dynamics Kernel..."}

    params = data.get("parameters", {})
    raw = data.get("raw_query", "").lower()
    pt = data.get("problem_type", "").lower()

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


async def solve_flow_meter(params):
    yield {"type": "step", "content": "Evaluating venturi/orifice meter performance..."}
    rho = float(params.get("rho", WATER_DENSITY))
    d1 = float(params.get("d1", 0.1))
    d2 = float(params.get("d2", 0.05))
    dp = float(params.get("dp", params.get("delta_p", 1000)))
    cd = float(params.get("cd", 0.98))

    a1 = np.pi * (d1 / 2) ** 2
    a2 = np.pi * (d2 / 2) ** 2
    beta = d2 / d1
    q = cd * a2 * np.sqrt((2 * dp) / (rho * (1 - beta ** 4)))
    v2 = q / a2

    x = np.array([d1, d2])
    y = np.array([q / a1, v2])
    yield {"type": "diagram", "diagram_type": "pressure_curve", "data": series_points(x, y)}

    yield {"type": "final", "answer": f"### Flow Meter Analysis\n- Inlet diameter: {d1:.4f} m\n- Throat diameter: {d2:.4f} m\n- Pressure drop: {dp:.2f} Pa\n- Discharge coefficient: {cd:.3f}\n- Flow rate: {q:.6f} m^3/s\n- Throat velocity: {v2:.4f} m/s"}


async def solve_hydrostatics(params, raw_query=""):
    yield {"type": "step", "content": "Computing hydrostatic pressure variation with depth..."}
    h = float(params.get("h", params.get("depth", 1)))
    rho = float(params.get("rho", WATER_DENSITY))
    g = float(params.get("g", G))

    p_gauge = rho * g * h
    depths = np.linspace(0, max(h, 1e-6), 60)
    pressures = rho * g * depths / 1000
    yield {"type": "diagram", "diagram_type": "pressure_curve", "data": series_points(depths, pressures)}

    steps = [
        "### Hydrostatic Analysis",
        f"- Depth: {h:.4f} m",
        f"- Density: {rho:.2f} kg/m^3",
        f"- Gauge pressure: {p_gauge:.2f} Pa",
        f"- Gauge pressure: {p_gauge / 1000:.4f} kPa",
    ]
    if raw_query:
        if "add more water" in raw_query:
            steps.append("- Adding more water increases the pressure because pressure grows with liquid height.")
        if "vegetable oil" in raw_query:
            steps.append("- For the same height, vegetable oil gives a lower pressure because its density is lower than water.")
        if "bubble" in raw_query:
            steps.append("- The air bubble expands as it rises because the surrounding pressure decreases toward the surface.")
        if "hole at the bottom" in raw_query:
            steps.append("- Water flows out fastest at first because the pressure head is largest, then slows down as the water level drops.")
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
    g = float(params.get("g", G))

    p2 = None if p2 in (None, "") else float(p2)
    v2 = None if v2 in (None, "") else float(v2)

    total_head_1 = p1 / (rho * g) + (v1 ** 2) / (2 * g) + h1
    if p2 is None and v2 is not None:
        p2 = rho * g * (total_head_1 - (v2 ** 2) / (2 * g) - h2)
    elif v2 is None and p2 is not None:
        v2_head = max(0.0, 2 * g * (total_head_1 - p2 / (rho * g) - h2))
        v2 = np.sqrt(v2_head)
    elif p2 is None and v2 is None:
        yield {"type": "final", "answer": "Provide either the downstream pressure or downstream velocity for Bernoulli analysis."}
        return

    heads_x = np.array([1, 2, 3])
    heads_y = np.array([
        p1 / (rho * g),
        (v1 ** 2) / (2 * g),
        h1,
    ])
    yield {"type": "diagram", "diagram_type": "energy_curve", "data": series_points(heads_x, heads_y)}

    steps = [
        "### Bernoulli Resolution",
        f"- Upstream total head: {total_head_1:.4f} m",
        f"- Downstream velocity: {v2:.4f} m/s",
        f"- Downstream pressure: {p2:.2f} Pa",
        f"- Downstream pressure: {p2 / 1000:.4f} kPa",
    ]
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_pipe_flow(params):
    yield {"type": "step", "content": "Evaluating Reynolds number and pipe-flow regime..."}
    v = float(params.get("v", 1))
    d = float(params.get("d", params.get("D", 0.1)))
    rho = float(params.get("rho", WATER_DENSITY))
    mu = float(params.get("mu", WATER_VISCOSITY))

    re = (rho * v * d) / mu if mu else 0.0
    regime = "Laminar" if re < 2300 else "Turbulent" if re > 4000 else "Transitional"

    velocities = np.linspace(0.1, max(v * 1.5, 0.2), 60)
    reynolds = (rho * velocities * d) / mu if mu else np.zeros_like(velocities)
    yield {"type": "diagram", "diagram_type": "pressure_curve", "data": series_points(velocities, reynolds)}

    yield {"type": "final", "answer": f"### Pipe Flow Diagnostics\n- Velocity: {v:.4f} m/s\n- Diameter: {d:.4f} m\n- Reynolds number: {re:.2f}\n- Regime: **{regime}**"}


async def solve_head_loss(params):
    yield {"type": "step", "content": "Calculating Darcy-Weisbach head loss profile..."}
    L = float(params.get("L", params.get("l", 100)))
    d = float(params.get("d", params.get("D", 0.1)))
    v = float(params.get("v", 2))
    f = float(params.get("f", 0.02))
    g = float(params.get("g", G))

    hf = f * (L / d) * (v ** 2 / (2 * g))
    x = np.linspace(0, L, 80)
    y = hf * (x / L) if L else np.zeros_like(x)
    yield {"type": "diagram", "diagram_type": "pressure_curve", "data": series_points(x, y)}

    steps = [
        "### Head Loss Analysis",
        f"- Pipe length: {L:.4f} m",
        f"- Diameter: {d:.4f} m",
        f"- Velocity: {v:.4f} m/s",
        f"- Friction factor: {f:.5f}",
        f"- Head loss: {hf:.5f} m",
        f"- Pressure drop: {WATER_DENSITY * g * hf:.2f} Pa",
    ]
    yield {"type": "final", "answer": "\n".join(steps)}


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
