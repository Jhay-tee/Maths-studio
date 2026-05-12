import asyncio
import numpy as np
from solvers.constants import G


def series_points(x_values, y_values):
    return [{"x": float(x), "y": float(y)} for x, y in zip(x_values, y_values)]


async def solve_mechanics(data):
    yield {"type": "step", "content": "Initializing Classical Mechanics Kernel..."}

    params = data.get("parameters", {})
    pt = data.get("problem_type", "").lower()
    raw = data.get("raw_query", "").lower()
    params["method"] = data.get("requested_method") or params.get("method") or "governing equations"

    try:
        if "projectile" in pt or "projectile" in raw:
            async for chunk in solve_projectile(params):
                yield chunk
        elif any(keyword in pt or keyword in raw for keyword in ["kinematics", "motion", "suvat"]):
            async for chunk in solve_kinematics(params):
                yield chunk
        elif any(keyword in pt or keyword in raw for keyword in ["static", "equilibrium", "reaction"]):
            async for chunk in solve_statics(params):
                yield chunk
        elif any(keyword in pt or keyword in raw for keyword in ["energy", "work", "power"]):
            async for chunk in solve_work_energy(params):
                yield chunk
        elif any(keyword in pt or keyword in raw for keyword in ["force", "newton", "dynamics"]):
            async for chunk in solve_dynamics(params):
                yield chunk
        elif any(keyword in pt or keyword in raw for keyword in ["vibration", "harmonic", "spring", "oscillation"]):
            async for chunk in solve_vibrations(params):
                yield chunk
        elif any(keyword in pt or keyword in raw for keyword in ["rotation", "angular", "torque"]):
            async for chunk in solve_rotation(params):
                yield chunk
        else:
            yield {"type": "step", "content": "Applying a general mechanics interpretation..."}
            yield {"type": "final", "answer": "Mechanics problem detected, but I need a more specific setup such as motion, statics, rotation, work-energy, projectile, or vibration."}
    except Exception as e:
        yield {"type": "final", "answer": f"Mechanics Solver Error: {str(e)}"}


async def solve_projectile(params):
    yield {"type": "step", "content": "Analyzing projectile trajectory and flight envelope..."}

    v0 = float(params.get("v0", params.get("velocity", 0)))
    theta_deg = float(params.get("theta", params.get("angle", 0)))
    y0 = float(params.get("y0", params.get("h0", 0)))
    g = float(params.get("g", G))

    if v0 <= 0:
        yield {"type": "final", "answer": "Error: initial velocity must be greater than zero."}
        return

    theta_rad = np.radians(theta_deg)
    vx = v0 * np.cos(theta_rad)
    vy = v0 * np.sin(theta_rad)

    coeffs = [-0.5 * g, vy, y0]
    roots = np.roots(coeffs)
    positive_roots = [float(root.real) for root in roots if abs(root.imag) < 1e-9 and root.real >= 0]
    t_flight = max(positive_roots) if positive_roots else 0.0
    h_max = y0 + (vy ** 2) / (2 * g)
    t_peak = vy / g if g else 0.0
    range_x = vx * t_flight

    t = np.linspace(0, max(t_flight, 1e-6), 120)
    x = vx * t
    y = y0 + vy * t - 0.5 * g * t ** 2

    yield {"type": "diagram", "diagram_type": "trajectory", "data": {"x": x.tolist(), "y": y.tolist()}}

    steps = [
        "### Projectile Motion Report",
        f"**Method Used:** {params.get('method', 'governing equations').title()}",
        f"- Initial speed: {v0:.3f} m/s",
        f"- Launch angle: {theta_deg:.3f} deg",
        f"- Initial height: {y0:.3f} m",
        "#### Resolved Components",
        f"- Horizontal velocity: $v_x = v_0 \\cos\\theta = {vx:.3f}$ m/s",
        f"- Vertical velocity: $v_y = v_0 \\sin\\theta = {vy:.3f}$ m/s",
        "#### Flight Results",
        f"- Time to peak: {t_peak:.3f} s",
        f"- Total flight time: {t_flight:.3f} s",
        f"- Maximum height: {h_max:.3f} m",
        f"- Horizontal range: {range_x:.3f} m",
    ]
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_kinematics(params):
    yield {"type": "step", "content": "Applying constant-acceleration equations of motion..."}

    u = params.get("u", params.get("initial_velocity"))
    v = params.get("v", params.get("final_velocity"))
    a = params.get("a", params.get("acceleration"))
    t = params.get("t", params.get("time"))
    s = params.get("s", params.get("displacement"))

    values = {key: None if value in (None, "") else float(value) for key, value in {"u": u, "v": v, "a": a, "t": t, "s": s}.items()}

    if values["v"] is None and None not in (values["u"], values["a"], values["t"]):
        values["v"] = values["u"] + values["a"] * values["t"]
    if values["s"] is None and None not in (values["u"], values["a"], values["t"]):
        values["s"] = values["u"] * values["t"] + 0.5 * values["a"] * values["t"] ** 2
    if values["a"] is None and None not in (values["u"], values["v"], values["t"]) and values["t"] != 0:
        values["a"] = (values["v"] - values["u"]) / values["t"]
    if values["u"] is None and None not in (values["v"], values["a"], values["t"]):
        values["u"] = values["v"] - values["a"] * values["t"]
    if values["t"] is None and None not in (values["u"], values["v"], values["a"]) and values["a"] != 0:
        values["t"] = (values["v"] - values["u"]) / values["a"]

    resolved = [f"- {key} = {value:.4f}" for key, value in values.items() if value is not None]
    if values["t"] is not None and values["u"] is not None and values["a"] is not None:
        t_series = np.linspace(0, max(values["t"], 1e-6), 80)
        s_series = values["u"] * t_series + 0.5 * values["a"] * t_series ** 2
        yield {"type": "diagram", "diagram_type": "displacement_curve", "data": series_points(t_series, s_series)}

    steps = [
        "### Linear Kinematics Analysis",
        f"**Method Used:** {params.get('method', 'governing equations').title()}",
        "#### Solved State",
        *resolved,
        "#### Governing Relations",
        "- $v = u + at$",
        "- $s = ut + \\frac{1}{2}at^2$",
        "- $v^2 = u^2 + 2as$",
    ]
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_statics(params):
    yield {"type": "step", "content": "Resolving forces and moments from equilibrium..."}

    m = float(params.get("moment", params.get("M", 0)))
    w = float(params.get("w", 0))
    L = float(params.get("L", params.get("l", 1)))
    P = float(params.get("P", params.get("point_load", 0)))
    a = float(params.get("a", L / 2))

    total_load = P + w * L
    moment_about_a = P * a + (w * L) * (L / 2) + m
    rb = moment_about_a / L if L else 0.0
    ra = total_load - rb

    x = np.linspace(0, L, 100)
    shear = ra - np.where(x >= a, P, 0) - w * x
    yield {"type": "diagram", "diagram_type": "force_curve", "data": series_points(x, shear)}

    steps = [
        "### Statics Equilibrium Report",
        f"**Method Used:** {params.get('method', 'equilibrium equations').title()}",
        f"- Span length: {L:.3f} m",
        f"- Point load: {P:.3f} N at {a:.3f} m",
        f"- Uniform load: {w:.3f} N/m",
        f"- Applied moment: {m:.3f} N·m",
        "#### Support Reactions",
        f"- Left reaction: {ra:.3f} N",
        f"- Right reaction: {rb:.3f} N",
    ]
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_work_energy(params):
    yield {"type": "step", "content": "Applying work-energy and power relations..."}

    F = float(params.get("F", params.get("force", 0)))
    s = float(params.get("s", params.get("distance", 0)))
    m = float(params.get("m", params.get("mass", 0)))
    u = float(params.get("u", 0))
    v = float(params.get("v", 0))
    t = float(params.get("t", 0))

    work = F * s
    delta_ke = 0.5 * m * (v ** 2 - u ** 2) if m > 0 else 0.0
    power = work / t if t > 0 else None

    x = np.linspace(0, max(s, 1e-6), 60)
    work_curve = F * x
    yield {"type": "diagram", "diagram_type": "energy_curve", "data": series_points(x, work_curve)}

    steps = [
        "### Work-Energy Analysis",
        f"**Method Used:** {params.get('method', 'work-energy theorem').title()}",
        f"- Work done: {work:.3f} J",
        f"- Change in kinetic energy: {delta_ke:.3f} J",
    ]
    if power is not None:
        steps.append(f"- Average power: {power:.3f} W")
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_dynamics(params):
    yield {"type": "step", "content": "Solving Newton's second-law relations..."}
    m = float(params.get("m", params.get("mass", 1)))
    f = float(params.get("f", params.get("F", params.get("force", 0))))

    if m <= 0:
        yield {"type": "final", "answer": "Error: mass must be positive for dynamic analysis."}
        return

    a = f / m
    diagram_data = {
        "force": f,
        "mass": m,
        "acceleration": a,
        "scale": max(abs(f), 1),
    }
    yield {"type": "diagram", "diagram_type": "force_diagram", "data": diagram_data}
    yield {"type": "final", "answer": f"### Dynamics Resolution\n**Method Used:** {params.get('method', 'governing equations').title()}\nMass: {m} kg\nForce: {f} N\nAcceleration: $a = F/m = {a:.3f}$ m/s$^2$"}


async def solve_vibrations(params):
    yield {"type": "step", "content": "Analyzing simple harmonic motion response..."}
    k = float(params.get("k", params.get("stiffness", 100)))
    m = float(params.get("m", params.get("mass", 1)))
    c = float(params.get("c", params.get("damping", 0)))
    A = float(params.get("A", params.get("amplitude", 0.1)))

    wn = np.sqrt(k / m)
    zeta = c / (2 * np.sqrt(k * m)) if k > 0 and m > 0 else 0.0
    wd = wn * np.sqrt(max(0.0, 1 - zeta ** 2))
    fn = wn / (2 * np.pi)
    period = 1 / fn if fn else 0.0

    t_response = np.linspace(0, max(3 * period, 1.0), 250)
    if zeta < 1:
        x_response = A * np.exp(-zeta * wn * t_response) * np.cos(wd * t_response)
    else:
        x_response = A * np.exp(-wn * t_response)

    yield {"type": "diagram", "diagram_type": "vibration_response", "data": {"t": t_response.tolist(), "x": x_response.tolist(), "period": period}}

    steps = [
        "### Vibration Analysis",
        f"**Method Used:** {params.get('method', 'governing equations').title()}",
        f"- Natural frequency: {wn:.4f} rad/s",
        f"- Damping ratio: {zeta:.4f}",
        f"- Damped frequency: {wd:.4f} rad/s",
        f"- Period: {period:.4f} s",
    ]
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_rotation(params):
    yield {"type": "step", "content": "Applying rotational dynamics and angular motion relations..."}
    torque = float(params.get("torque", params.get("tau", 0)))
    inertia = float(params.get("inertia", params.get("I", 1)))
    omega0 = float(params.get("omega0", params.get("omega_initial", 0)))
    t = float(params.get("t", 0))

    if inertia <= 0:
        yield {"type": "final", "answer": "Error: moment of inertia must be positive."}
        return

    alpha = torque / inertia
    omega = omega0 + alpha * t
    theta = omega0 * t + 0.5 * alpha * t ** 2

    if t > 0:
        ts = np.linspace(0, t, 80)
        omega_curve = omega0 + alpha * ts
        yield {"type": "diagram", "diagram_type": "angular_velocity_curve", "data": series_points(ts, omega_curve)}

    answer = [
        "### Rotational Dynamics",
        f"**Method Used:** {params.get('method', 'governing equations').title()}",
        f"- Angular acceleration: {alpha:.4f} rad/s^2",
        f"- Final angular velocity: {omega:.4f} rad/s",
        f"- Angular displacement: {theta:.4f} rad",
    ]
    yield {"type": "final", "answer": "\n".join(answer)}
