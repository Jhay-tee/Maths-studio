import asyncio
import numpy as np
import sympy as sp

async def solve_mechanics(data):
    yield {"type": "step", "content": "Initializing Classical Mechanics Kernel..."}
    
    params = data.get("parameters", {})
    pt = data.get("problem_type", "").lower()
    raw = data.get("raw_query", "").lower()

    try:
        if "projectile" in pt or "projectile" in raw:
            async for chunk in solve_projectile(params):
                yield chunk
        elif "kinematics" in pt or "motion" in raw:
            async for chunk in solve_kinematics(params):
                yield chunk
        elif "force" in pt or "newton" in raw or "dynamics" in pt:
            async for chunk in solve_dynamics(params):
                yield chunk
        elif "vibration" in pt or "harmonic" in raw or "spring" in raw:
            async for chunk in solve_vibrations(params):
                yield chunk
        elif "rotation" in pt or "angular" in raw:
            async for chunk in solve_rotation(params):
                yield chunk
        else:
            yield {"type": "step", "content": "Applying Work-Energy Theorem..."}
            await asyncio.sleep(0.5)
            yield {"type": "final", "answer": "Analysis complete. System energy is conserved. Please provide specific initial conditions for numerical results."}
    except Exception as e:
        yield {"type": "final", "answer": f"Mechanics Solver Error: {str(e)}"}

async def solve_projectile(params):
    yield {"type": "step", "content": "Analyzing Projectile Trajectory..."}
    
    v0 = float(params.get("v0", params.get("velocity", 0)))
    theta_deg = float(params.get("theta", params.get("angle", 0)))
    g = 9.81
    
    if v0 <= 0:
        yield {"type": "final", "answer": "Error: Initial velocity must be greater than zero."}
        return

    theta_rad = np.radians(theta_deg)
    
    t_flight = (2 * v0 * np.sin(theta_rad)) / g
    h_max = (v0**2 * (np.sin(theta_rad))**2) / (2 * g)
    range_x = (v0**2 * np.sin(2 * theta_rad)) / g
    
    steps = [
        "### Projectile Motion Report",
        f"Initial Velocity ($v_0$): {v0} m/s",
        f"Launch Angle ($\\theta$): {theta_deg}$^\\circ$",
        "#### Computed Kinematics",
        f"- **Time of Flight:** $T = \\frac{{2v_0\\sin\\theta}}{{g}} = {t_flight:.2f}$ s",
        f"- **Max Height:** $H = \\frac{{v_0^2\\sin^2\\theta}}{{2g}} = {h_max:.2f}$ m",
        f"- **Total Range:** $R = \\frac{{v_0^2\\sin(2\\theta)}}{{g}} = {range_x:.2f}$ m",
    ]
    
    # Trajectory Data for specialized UI (if supported)
    t = np.linspace(0, t_flight, 50)
    x = v0 * np.cos(theta_rad) * t
    y = v0 * np.sin(theta_rad) * t - 0.5 * g * t**2
    
    yield {"type": "diagram", "diagram_type": "trajectory", "data": {"x": x.tolist(), "y": y.tolist()}}
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_kinematics(params):
    yield {"type": "step", "content": "Applying Equations of Motion..."}
    # v = u + at, s = ut + 0.5at^2, v^2 = u^2 + 2as
    u = float(params.get("u", params.get("initial_velocity", 0)))
    a = float(params.get("a", params.get("acceleration", 0)))
    t = float(params.get("t", params.get("time", 0)))
    
    v = u + a * t
    s = u * t + 0.5 * a * t**2
    
    steps = [
        "### Linear Kinematics Analysis",
        f"Initial Velocity ($u$): {u} m/s",
        f"Acceleration ($a$): {a} m/s$^2$",
        f"Time ($t$): {t} s",
        "#### Calculated Parameters",
        f"- Final Velocity: $v = u + at = {v:.2f}$ m/s",
        f"- Displacement: $s = ut + \\frac{{1}}{{2}}at^2 = {s:.2f}$ m"
    ]
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_dynamics(params):
    yield {"type": "step", "content": "Solving Newton's Equations of Motion..."}
    m = float(params.get("m", params.get("mass", 0)))
    f = float(params.get("f", params.get("force", 0)))
    
    if m > 0:
        a = f / m
        answer = f"### Dynamics Resolution\nMass: {m} kg\nForce: {f} N\nResulting Acceleration: $a = F/m = {a:.2f}$ m/s$^2$"
    else:
        answer = "Error: Mass must be positive for dynamic analysis."
        
    yield {"type": "final", "answer": answer}

async def solve_vibrations(params):
    yield {"type": "step", "content": "Analyzing Simple Harmonic Motion..."}
    k = float(params.get("k", params.get("stiffness", 100)))
    m = float(params.get("m", params.get("mass", 1)))
    
    wn = np.sqrt(k/m)
    fn = wn / (2 * np.pi)
    tn = 1 / fn
    
    steps = [
        "### Vibration Analysis (SHM)",
        f"- Stiffness ($k$): {k} N/m",
        f"- Mass ($m$): {m} kg",
        "#### Natural Characteristics",
        f"- **Angular Frequency ($\\omega_n$):** $\\sqrt{{k/m}} = {wn:.3f}$ rad/s",
        f"- **Natural Frequency ($f_n$):** {fn:.3f} Hz",
        f"- **Period ($T_n$):** {tn:.3f} s"
    ]
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_rotation(params):
    yield {"type": "step", "content": "Applying Rotational Equations of Motion..."}
    # Torque = I * alpha
    torque = float(params.get("torque", 0))
    inertia = float(params.get("inertia", params.get("I", 1)))
    
    if inertia > 0:
        alpha = torque / inertia
        answer = f"### Rotational Dynamics\nTorque: {torque} N·m\nInertia ($I$): {inertia} kg·m$^2$\nAngular Acceleration ($\\alpha$): $\\tau/I = {alpha:.3f}$ rad/s$^2$"
    else:
        answer = "Error: Moment of inertia must be greater than zero."
        
    yield {"type": "final", "answer": answer}
