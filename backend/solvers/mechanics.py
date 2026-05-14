"""
Classical Mechanics Solver
Handles: projectile, kinematics, statics, contact forces,
         work-energy, dynamics, vibrations, rotation.
"""

import asyncio
import numpy as np
from solvers.constants import G
from solvers.utils import normalize_params, validate_physical_params, propagate_uncertainty


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def series_points(x_values, y_values):
    """Return a list of {x, y} dicts for diagram payloads."""
    return [{"x": float(x), "y": float(y)} for x, y in zip(x_values, y_values)]


def _extract_first_number(text, fallback=None):
    """Pull the first numeric token from *text*, return *fallback* if none."""
    import re
    match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text or "")
    return float(match.group()) if match else fallback


def _safe_float(value, default=0.0):
    """Convert *value* to float, returning *default* on failure."""
    try:
        return float(value) if value not in (None, "", "None") else default
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

async def solve_mechanics(data):
    yield {"type": "step", "content": "Initializing Classical Mechanics Kernel..."}

    params = normalize_params(data.get("parameters", {}))

    is_valid, err = validate_physical_params(params)
    if not is_valid:
        yield {"type": "error", "message": err}
        return

    pt  = data.get("problem_type", "").lower()
    raw = data.get("raw_query",    "").lower()

    used_vars = [k for k, v in params.items() if v is not None]
    if used_vars:
        yield {"type": "step", "content": f"Parameters detected: {', '.join(used_vars)}"}

    try:
        if "projectile" in pt or "projectile" in raw:
            async for chunk in solve_projectile(params):
                yield chunk

        elif any(kw in pt or kw in raw for kw in ("kinematics", "motion", "suvat")):
            async for chunk in solve_kinematics(params):
                yield chunk

        elif any(kw in pt or kw in raw
                 for kw in ("static_friction", "friction", "normal force", "book", "table")):
            async for chunk in solve_contact_forces(params, raw):
                yield chunk

        elif any(kw in pt or kw in raw for kw in ("static", "equilibrium", "reaction")):
            async for chunk in solve_statics(params):
                yield chunk

        elif any(kw in pt or kw in raw for kw in ("energy", "work", "power")):
            async for chunk in solve_work_energy(params):
                yield chunk

        elif any(kw in pt or kw in raw for kw in ("force", "newton", "dynamics")):
            async for chunk in solve_dynamics(params):
                yield chunk

        elif any(kw in pt or kw in raw
                 for kw in ("vibration", "harmonic", "spring", "oscillation")):
            async for chunk in solve_vibrations(params):
                yield chunk

        elif any(kw in pt or kw in raw for kw in ("rotation", "angular", "torque")):
            async for chunk in solve_rotation(params):
                yield chunk

        else:
            yield {"type": "step",
                   "content": "Applying a general mechanics interpretation..."}
            yield {"type": "final",
                   "answer": (
                       "Mechanics problem detected, but a more specific setup is needed "
                       "— e.g. motion, statics, rotation, work-energy, projectile, or vibration."
                   )}

    except Exception as exc:
        yield {"type": "final", "answer": f"Mechanics Solver Error: {exc}"}


# ---------------------------------------------------------------------------
# Sub-solvers
# ---------------------------------------------------------------------------

async def solve_projectile(params):
    yield {"type": "step", "content": "Analyzing projectile flight geometry..."}

    v0        = _safe_float(params.get("v0",    params.get("velocity",  0)))
    theta_deg = _safe_float(params.get("theta", params.get("angle",     45)))
    y0        = _safe_float(params.get("y0",    params.get("h0",        0)))
    g         = _safe_float(params.get("g", G))

    if v0 <= 0:
        yield {"type": "final",
               "answer": "Error: initial velocity must be greater than zero."}
        return
    if g <= 0:
        yield {"type": "final",
               "answer": "Error: gravitational acceleration must be positive."}
        return

    yield {"type": "step",
           "content": "Evaluating equations of motion (Kinematic Ballistics)..."}

    theta_rad = np.radians(theta_deg)
    vx = v0 * np.cos(theta_rad)
    vy = v0 * np.sin(theta_rad)

    yield {"type": "step",
           "content": (f"Velocity components: $v_x = {vx:.4f}$ m/s, "
                       f"$v_y = {vy:.4f}$ m/s")}

    # Time of flight: solve -½g·t² + vy·t + y0 = 0
    discriminant = vy ** 2 + 2 * g * y0
    if discriminant < 0:
        yield {"type": "final",
               "answer": "Error: trajectory never reaches the ground with these parameters."}
        return

    t_flight = (vy + np.sqrt(discriminant)) / g      # larger positive root
    h_max    = y0 + (vy ** 2) / (2 * g)
    range_x  = vx * t_flight

    yield {"type": "step",
           "content": "Resolving polynomial coefficients for ground impact..."}

    t_arr = np.linspace(0, t_flight, 200)
    x_arr = vx * t_arr
    y_arr = y0 + vy * t_arr - 0.5 * g * t_arr ** 2

    yield {"type": "diagram",
           "diagram_type": "trajectory",
           "data": {"x": x_arr.tolist(), "y": y_arr.tolist()}}

    ans = [
        "### Projectile Ballistics Report",
        "#### Governing Equations",
        r"- **Trajectory:** $y(x) = y_0 + x\tan(\theta) - \frac{gx^2}{2v_0^2\cos^2(\theta)}$",
        r"- **Vertical Velocity:** $v_y(t) = v_0\sin(\theta) - gt$",
        "",
        "#### Kinematic Outcomes",
        f"- Initial velocity ($v_0$): {v0:.4f} m/s",
        f"- Launch angle ($\\theta$): {theta_deg:.2f}°",
        f"- Initial elevation ($y_0$): {y0:.4f} m",
        f"- Maximum altitude ($H_{{max}}$): {h_max:.4f} m",
        f"- Time of flight ($t_f$): {t_flight:.4f} s",
        f"- Horizontal range ($R$): {range_x:.4f} m",
    ]
    yield {"type": "final", "answer": "\n".join(ans)}


async def solve_kinematics(params):
    yield {"type": "step",
           "content": "Applying constant-acceleration equations of motion..."}

    raw_vals = {
        "u": params.get("u", params.get("initial_velocity")),
        "v": params.get("v", params.get("final_velocity")),
        "a": params.get("a", params.get("acceleration")),
        "t": params.get("t", params.get("time")),
        "s": params.get("s", params.get("displacement")),
    }
    # Convert to float or None
    vals = {k: (None if raw_vals[k] in (None, "", "None") else float(raw_vals[k]))
            for k in raw_vals}

    def known(*keys):
        return all(vals[k] is not None for k in keys)

    # Apply SUVAT relations iteratively until no new values can be derived
    changed = True
    while changed:
        changed = False
        if vals["v"] is None and known("u", "a", "t"):
            vals["v"] = vals["u"] + vals["a"] * vals["t"];  changed = True
        if vals["s"] is None and known("u", "a", "t"):
            vals["s"] = vals["u"] * vals["t"] + 0.5 * vals["a"] * vals["t"] ** 2; changed = True
        if vals["s"] is None and known("u", "v", "t"):
            vals["s"] = 0.5 * (vals["u"] + vals["v"]) * vals["t"];               changed = True
        if vals["a"] is None and known("u", "v", "t") and vals["t"] != 0:
            vals["a"] = (vals["v"] - vals["u"]) / vals["t"];                      changed = True
        if vals["a"] is None and known("u", "v", "s") and vals["s"] != 0:
            vals["a"] = (vals["v"] ** 2 - vals["u"] ** 2) / (2 * vals["s"]);     changed = True
        if vals["u"] is None and known("v", "a", "t"):
            vals["u"] = vals["v"] - vals["a"] * vals["t"];                        changed = True
        if vals["u"] is None and known("v", "a", "s") and vals["a"] != 0:
            disc = vals["v"] ** 2 - 2 * vals["a"] * vals["s"]
            if disc >= 0:
                vals["u"] = np.sqrt(disc) * np.sign(vals["v"]);                   changed = True
        if vals["t"] is None and known("u", "v", "a") and vals["a"] != 0:
            vals["t"] = (vals["v"] - vals["u"]) / vals["a"];                      changed = True
        if vals["t"] is None and known("u", "v", "s"):
            denom = vals["u"] + vals["v"]
            if denom != 0:
                vals["t"] = 2 * vals["s"] / denom;                                changed = True
        if vals["v"] is None and known("u", "a", "s"):
            disc = vals["u"] ** 2 + 2 * vals["a"] * vals["s"]
            if disc >= 0:
                vals["v"] = np.sqrt(disc);                                         changed = True

    resolved = [f"- **{k}** = {vals[k]:.6g}" for k in ("u", "v", "a", "t", "s")
                if vals[k] is not None]

    if known("t", "u", "a") and vals["t"] > 0:
        t_arr = np.linspace(0, vals["t"], 100)
        s_arr = vals["u"] * t_arr + 0.5 * vals["a"] * t_arr ** 2
        yield {"type": "diagram",
               "diagram_type": "displacement_curve",
               "data": series_points(t_arr, s_arr)}

    steps = [
        "### Linear Kinematics Analysis",
        f"**Method:** SUVAT iterative resolution",
        "#### Solved State",
        *resolved,
        "",
        "#### Governing Relations",
        r"- $v = u + at$",
        r"- $s = ut + \frac{1}{2}at^2$",
        r"- $v^2 = u^2 + 2as$",
        r"- $s = \frac{1}{2}(u+v)t$",
    ]
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_statics(params):
    yield {"type": "step",
           "content": "Resolving forces and moments from equilibrium..."}

    M = _safe_float(params.get("moment", params.get("M", 0)))
    w = _safe_float(params.get("w", 0))
    L = _safe_float(params.get("L", params.get("l", 1)))
    P = _safe_float(params.get("P", params.get("point_load", 0)))
    a = _safe_float(params.get("a", L / 2 if L else 0))

    if L <= 0:
        yield {"type": "final", "answer": "Error: span length L must be positive."}
        return

    total_load      = P + w * L
    moment_about_A  = P * a + (w * L) * (L / 2) + M
    rb = moment_about_A / L
    ra = total_load - rb

    x_arr   = np.linspace(0, L, 200)
    # Shear force diagram (beam with UDL + point load P at x=a)
    shear   = ra - w * x_arr - np.where(x_arr >= a, P, 0.0)
    # Bending moment diagram
    moment  = ra * x_arr - 0.5 * w * x_arr ** 2 - np.where(x_arr >= a, P * (x_arr - a), 0.0) + M

    yield {"type": "diagram",
           "diagram_type": "shear_force",
           "data": series_points(x_arr, shear)}
    yield {"type": "diagram",
           "diagram_type": "bending_moment",
           "data": series_points(x_arr, moment)}

    max_moment   = float(np.max(np.abs(moment)))
    max_shear    = float(np.max(np.abs(shear)))

    steps = [
        "### Statics Equilibrium Report",
        f"- Span length ($L$): {L:.4f} m",
        f"- Point load ($P$): {P:.4f} N at $a$ = {a:.4f} m",
        f"- Uniform distributed load ($w$): {w:.4f} N/m",
        f"- Applied moment ($M$): {M:.4f} N·m",
        "",
        "#### Support Reactions",
        f"- Left reaction ($R_A$): {ra:.4f} N",
        f"- Right reaction ($R_B$): {rb:.4f} N",
        "",
        "#### Peak Internal Forces",
        f"- Maximum shear force: {max_shear:.4f} N",
        f"- Maximum bending moment: {max_moment:.4f} N·m",
    ]
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_contact_forces(params, raw_query):
    yield {"type": "step",
           "content": "Identifying contact forces and static-friction limits..."}

    m            = _safe_float(params.get("m", params.get("mass",
                    _extract_first_number(raw_query, 1.0))))
    g_val        = _safe_float(params.get("g", G))
    horiz_push   = _safe_float(params.get("F", params.get("force", 0)))
    mu_s         = _safe_float(params.get("mu_s",
                    params.get("coefficient_static_friction",
                    params.get("mu", 0))))
    theta_deg    = _safe_float(params.get("theta", params.get("angle", 0)))

    if m <= 0:
        yield {"type": "final",
               "answer": "Error: mass must be positive."}
        return

    theta_rad   = np.radians(theta_deg)
    weight      = m * g_val
    normal      = weight * np.cos(theta_rad)      # works for inclined planes too
    gravity_par = weight * np.sin(theta_rad)       # component along incline

    friction_limit = mu_s * normal if mu_s > 0 else None

    answer = [
        "### Contact Force Analysis",
        f"- Mass ($m$): {m:.4f} kg",
        f"- Weight ($W = mg$): {weight:.4f} N",
        f"- Normal force ($N$): {normal:.4f} N",
    ]

    if theta_deg != 0:
        answer.append(f"- Incline angle ($\\theta$): {theta_deg:.2f}°")
        answer.append(f"- Gravity component along surface: {gravity_par:.4f} N")

    if horiz_push > 0:
        net_drive   = horiz_push + gravity_par       # both drive sliding
        answer.append(f"- Applied push ($F$): {horiz_push:.4f} N")
        answer.append(
            f"- Static friction required to prevent sliding: {net_drive:.4f} N"
        )

    if friction_limit is not None:
        is_sliding = (horiz_push + gravity_par) > friction_limit
        answer.extend([
            "",
            f"- Maximum static friction ($f_{{s,max}} = \\mu_s N$): {friction_limit:.4f} N",
            f"- Object status: {'**SLIDES** (applied force exceeds friction limit)' if is_sliding else '**STATIC** (friction limit not exceeded)'}",
        ])

    yield {"type": "final", "answer": "\n".join(answer)}


async def solve_work_energy(params):
    yield {"type": "step",
           "content": "Applying work-energy and power relations..."}

    F  = _safe_float(params.get("F", params.get("force",    0)))
    s  = _safe_float(params.get("s", params.get("distance", 0)))
    m  = _safe_float(params.get("m", params.get("mass",     0)))
    u  = _safe_float(params.get("u", 0))
    v  = _safe_float(params.get("v", 0))
    t  = _safe_float(params.get("t", 0))
    h  = _safe_float(params.get("h", params.get("height",   0)))   # for PE
    g_val = _safe_float(params.get("g", G))

    work        = F * s
    delta_ke    = 0.5 * m * (v ** 2 - u ** 2) if m > 0 else 0.0
    delta_pe    = m * g_val * h             if m > 0 else 0.0
    power       = work / t                  if t  > 0 else None
    efficiency  = (delta_ke / work * 100)   if work != 0 else None

    if s > 0:
        x_arr      = np.linspace(0, s, 100)
        work_curve = F * x_arr
        yield {"type": "diagram",
               "diagram_type": "energy_curve",
               "data": series_points(x_arr, work_curve)}

    steps = [
        "### Work-Energy Analysis",
        f"- Applied force ($F$): {F:.4f} N",
        f"- Displacement ($s$): {s:.4f} m",
        f"- Work done ($W = Fs$): {work:.4f} J",
        f"- Change in kinetic energy ($\\Delta KE$): {delta_ke:.4f} J",
    ]
    if h != 0:
        steps.append(f"- Change in potential energy ($\\Delta PE = mgh$): {delta_pe:.4f} J")
    if power is not None:
        steps.append(f"- Average power ($P = W/t$): {power:.4f} W")
    if efficiency is not None:
        steps.append(f"- Work-to-KE efficiency: {efficiency:.2f}%")

    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_dynamics(params):
    yield {"type": "step",
           "content": "Solving Newton's second-law relations..."}

    m      = _safe_float(params.get("m", params.get("mass",  1)))
    f_net  = _safe_float(params.get("f", params.get("F", params.get("force", 0))))
    mu_k   = _safe_float(params.get("mu_k", params.get("mu", 0)))
    g_val  = _safe_float(params.get("g", G))

    if m <= 0:
        yield {"type": "final",
               "answer": "Error: mass must be positive for dynamic analysis."}
        return

    friction_force = mu_k * m * g_val
    net_force      = f_net - friction_force
    a              = net_force / m

    diagram_data = {
        "force":        f_net,
        "friction":     friction_force,
        "net_force":    net_force,
        "mass":         m,
        "acceleration": a,
        "scale":        max(abs(f_net), 1),
    }
    yield {"type": "diagram",
           "diagram_type": "force_diagram",
           "data": diagram_data}

    steps = [
        "### Dynamics — Newton's Second Law",
        f"- Mass ($m$): {m:.4f} kg",
        f"- Applied force ($F$): {f_net:.4f} N",
    ]
    if mu_k > 0:
        steps.append(f"- Kinetic friction ($f_k = \\mu_k mg$): {friction_force:.4f} N")
        steps.append(f"- Net force ($F_{{net}}$): {net_force:.4f} N")
    steps.append(f"- Acceleration ($a = F_{{net}}/m$): **{a:.6f} m/s²**")

    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_vibrations(params):
    yield {"type": "step",
           "content": "Analyzing simple harmonic / damped oscillation response..."}

    k  = _safe_float(params.get("k", params.get("stiffness", 100)))
    m  = _safe_float(params.get("m", params.get("mass",      1)))
    c  = _safe_float(params.get("c", params.get("damping",   0)))
    A  = _safe_float(params.get("A", params.get("amplitude", 0.1)))

    if m <= 0 or k <= 0:
        yield {"type": "final",
               "answer": "Error: mass and stiffness must both be positive."}
        return

    wn      = np.sqrt(k / m)
    c_cr    = 2 * np.sqrt(k * m)
    zeta    = c / c_cr if c_cr > 0 else 0.0
    wd      = wn * np.sqrt(max(0.0, 1 - zeta ** 2))
    fn      = wn / (2 * np.pi)
    period  = 1 / fn if fn else 0.0

    # Simulate 5 cycles (or at least 1 s)
    t_end      = max(5 * period, 1.0)
    t_response = np.linspace(0, t_end, 500)

    if zeta < 1:          # under-damped
        x_response = A * np.exp(-zeta * wn * t_response) * np.cos(wd * t_response)
    elif zeta == 1:       # critically damped
        x_response = A * (1 + wn * t_response) * np.exp(-wn * t_response)
    else:                 # over-damped
        r1 = -wn * (zeta - np.sqrt(zeta ** 2 - 1))
        r2 = -wn * (zeta + np.sqrt(zeta ** 2 - 1))
        # Initial conditions: x(0)=A, x'(0)=0
        C2 = A * r1 / (r1 - r2)
        C1 = A - C2
        x_response = C1 * np.exp(r1 * t_response) + C2 * np.exp(r2 * t_response)

    yield {"type": "diagram",
           "diagram_type": "vibration_response",
           "data": {"t": t_response.tolist(),
                    "x": x_response.tolist(),
                    "period": period}}

    regime = ("Under-damped"    if zeta < 1
              else "Critically damped" if zeta == 1
              else "Over-damped")

    steps = [
        "### Vibration Analysis",
        f"- Stiffness ($k$): {k:.4f} N/m",
        f"- Mass ($m$): {m:.4f} kg",
        f"- Damping coefficient ($c$): {c:.4f} N·s/m",
        f"- Critical damping ($c_{{cr}}$): {c_cr:.4f} N·s/m",
        f"- Natural frequency ($\\omega_n$): {wn:.6f} rad/s  /  {fn:.6f} Hz",
        f"- Damping ratio ($\\zeta$): {zeta:.6f}  → **{regime}**",
        f"- Damped frequency ($\\omega_d$): {wd:.6f} rad/s",
        f"- Period ($T$): {period:.6f} s",
    ]
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_rotation(params):
    yield {"type": "step",
           "content": "Applying rotational dynamics and angular motion relations..."}

    tau    = _safe_float(params.get("torque", params.get("tau",         0)))
    I      = _safe_float(params.get("inertia", params.get("I",          1)))
    omega0 = _safe_float(params.get("omega0", params.get("omega_initial", 0)))
    t      = _safe_float(params.get("t",                                 0))

    if I <= 0:
        yield {"type": "final",
               "answer": "Error: moment of inertia must be positive."}
        return

    alpha  = tau / I
    omega  = omega0 + alpha * t
    theta  = omega0 * t + 0.5 * alpha * t ** 2
    # Rotational kinetic energy
    KE_rot = 0.5 * I * omega ** 2

    if t > 0:
        ts          = np.linspace(0, t, 200)
        omega_curve = omega0 + alpha * ts
        theta_curve = omega0 * ts + 0.5 * alpha * ts ** 2
        yield {"type": "diagram",
               "diagram_type": "angular_velocity_curve",
               "data": series_points(ts, omega_curve)}
        yield {"type": "diagram",
               "diagram_type": "angular_displacement_curve",
               "data": series_points(ts, theta_curve)}

    answer = [
        "### Rotational Dynamics",
        f"- Torque ($\\tau$): {tau:.4f} N·m",
        f"- Moment of inertia ($I$): {I:.4f} kg·m²",
        f"- Angular acceleration ($\\alpha = \\tau/I$): {alpha:.6f} rad/s²",
        f"- Initial angular velocity ($\\omega_0$): {omega0:.4f} rad/s",
        f"- Final angular velocity ($\\omega$): {omega:.4f} rad/s",
        f"- Angular displacement ($\\theta$): {theta:.4f} rad",
        f"- Rotational kinetic energy ($KE = \\frac{{1}}{{2}}I\\omega^2$): {KE_rot:.4f} J",
    ]
    yield {"type": "final", "answer": "\n".join(answer)}
