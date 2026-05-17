"""
Fluid Dynamics Solver
Handles: Continuity, Bernoulli, Hydrostatics, Pipe Flow (Reynolds),
         Head Loss (Darcy-Weisbach), Venturi/Orifice meters, Pump Power.
"""

import numpy as np
from solvers.constants import WATER_DENSITY, WATER_VISCOSITY, G
from solvers.utils import normalize_params, validate_physical_params


def series_points(x_values, y_values):
    return [{"x": float(x), "y": float(y)} for x, y in zip(x_values, y_values)]


def _safe_float(value, default=0.0):
    try:
        return float(value) if value not in (None, "", "None") else default
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

async def solve_fluids(data):
    yield {"type": "step", "content": "Initializing Fluid Dynamics Kernel..."}

    params = normalize_params(data.get("parameters", {}))

    is_valid, err = validate_physical_params(params)
    if not is_valid:
        yield {"type": "error", "message": err}
        return

    raw = data.get("raw_query", "").lower()
    pt  = data.get("problem_type", "").lower()

    used_vars = [k for k, v in params.items() if v is not None]
    if used_vars:
        yield {"type": "step", "content": f"Boundary conditions detected: {', '.join(used_vars)}"}

    try:
        if any(kw in pt or kw in raw for kw in ("venturi", "orifice", "flow meter", "flow_meter")):
            async for chunk in solve_flow_meter(params):
                yield chunk
        elif any(kw in pt or kw in raw for kw in
                 ("manometer", "hydrostatic", "pressure at the bottom",
                  "bubble", "vegetable oil", "hole at the bottom")):
            async for chunk in solve_hydrostatics(params, raw):
                yield chunk
        elif "continuity" in pt or "continuity" in raw:
            async for chunk in solve_continuity(params):
                yield chunk
        elif any(kw in pt or kw in raw for kw in ("bernoulli", "energy equation")):
            async for chunk in solve_bernoulli(params):
                yield chunk
        elif any(kw in pt or kw in raw for kw in ("head loss", "darcy", "friction loss", "major loss")):
            async for chunk in solve_head_loss(params):
                yield chunk
        elif any(kw in pt or kw in raw for kw in ("pipe", "reynolds", "flow regime")):
            async for chunk in solve_pipe_flow(params):
                yield chunk
        elif any(kw in pt or kw in raw for kw in ("pump", "power", "hydraulic power")):
            async for chunk in solve_pump_power(params):
                yield chunk
        else:
            yield {
                "type": "final",
                "answer": (
                    "Fluid problem detected. I can solve: **Continuity**, **Bernoulli**, "
                    "**Hydrostatics**, **Pipe Flow / Reynolds Number**, "
                    "**Head Loss (Darcy-Weisbach)**, **Venturi/Orifice**, and **Pump Power**. "
                    "Please specify the flow type and parameters."
                ),
            }
    except Exception as e:
        yield {"type": "final", "answer": f"Fluids Solver Error: {str(e)}"}


# ---------------------------------------------------------------------------
# Sub-solvers
# ---------------------------------------------------------------------------

async def solve_continuity(params):
    yield {"type": "step", "content": "Applying continuity equation: $A_1 v_1 = A_2 v_2$"}

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
        a1 = np.pi * d1 ** 2 / 4
        yield {"type": "step",
               "content": f"$A_1 = \\pi d_1^2/4 = \\pi \\times {d1}^2/4 = {a1:.6f}$ m²"}
    if a2 is None and d2 is not None:
        a2 = np.pi * d2 ** 2 / 4
        yield {"type": "step",
               "content": f"$A_2 = \\pi d_2^2/4 = \\pi \\times {d2}^2/4 = {a2:.6f}$ m²"}

    if None not in (a1, v1, a2) and v2 is None and a2 != 0:
        v2 = a1 * v1 / a2
        yield {"type": "step",
               "content": f"$v_2 = A_1 v_1 / A_2 = {a1:.4e} \\times {v1} / {a2:.4e} = {v2:.4f}$ m/s"}
    elif None not in (a2, v2, a1) and v1 is None and a1 != 0:
        v1 = a2 * v2 / a1
        yield {"type": "step",
               "content": f"$v_1 = A_2 v_2 / A_1 = {a2:.4e} \\times {v2} / {a1:.4e} = {v1:.4f}$ m/s"}
    elif None not in (a1, v1, v2) and a2 is None and v2 != 0:
        a2 = a1 * v1 / v2
        yield {"type": "step",
               "content": f"$A_2 = A_1 v_1 / v_2 = {a1:.4e} \\times {v1} / {v2} = {a2:.6f}$ m²"}
    elif None not in (a2, v2, v1) and a1 is None and v1 != 0:
        a1 = a2 * v2 / v1
        yield {"type": "step",
               "content": f"$A_1 = A_2 v_2 / v_1 = {a2:.4e} \\times {v2} / {v1} = {a1:.6f}$ m²"}

    if None in (a1, a2, v1, v2):
        yield {
            "type": "final",
            "answer": (
                "Continuity equation needs at least **three** of: "
                "$A_1$, $v_1$, $A_2$, $v_2$ (or diameters $d_1$, $d_2$ in place of areas)."
            ),
        }
        return

    Q = a1 * v1
    yield {"type": "step", "content": f"Volume flow rate: $Q = A_1 v_1 = {Q:.6f}$ m³/s"}

    # Velocity vs section diagram
    yield {"type": "diagram", "diagram_type": "velocity_profile",
           "data": [{"r": 1.0, "v": float(v1)}, {"r": 2.0, "v": float(v2)}]}

    yield {
        "type": "final",
        "answer": "\n".join([
            "### Continuity Equation — $A_1 v_1 = A_2 v_2$",
            f"- Section 1: $A_1 = {a1:.6f}$ m²,  $v_1 = {v1:.4f}$ m/s",
            f"- Section 2: $A_2 = {a2:.6f}$ m²,  $v_2 = {v2:.4f}$ m/s",
            f"- Volume flow rate ($Q$): **{Q:.6f} m³/s**  ({Q * 1000:.4f} L/s)",
        ]),
    }


async def solve_hydrostatics(params, raw_query=""):
    yield {"type": "step", "content": "Computing hydrostatic pressure: $p = \\rho g h$"}

    h   = _safe_float(params.get("h", params.get("depth", 1.0)), 1.0)
    rho = _safe_float(params.get("rho", params.get("density", WATER_DENSITY)), WATER_DENSITY)
    g   = _safe_float(params.get("g",   9.81), 9.81)

    yield {"type": "step", "content": f"$\\rho = {rho}$ kg/m³,  $g = {g}$ m/s²,  $h = {h}$ m"}

    p_gauge = rho * g * h
    yield {"type": "step",
           "content": f"$p_{{gauge}} = \\rho g h = {rho} \\times {g} \\times {h} = {p_gauge:.4f}$ Pa"}

    # Uncertainty propagation (optional)
    uncertainties = {k.replace("_sigma", ""): v for k, v in params.items() if k.endswith("_sigma")}
    p_sigma = 0.0
    if uncertainties:
        try:
            from solvers.utils import propagate_uncertainty
            p_sigma = propagate_uncertainty(
                "rho * g * h", {"rho": rho, "g": g, "h": h}, uncertainties
            )
        except Exception:
            pass

    depths    = np.linspace(0, max(h, 1e-6), 60)
    pressures = rho * g * depths / 1000    # kPa
    yield {"type": "diagram", "diagram_type": "pressure_curve",
           "data": series_points(depths, pressures)}

    steps = [
        "### Hydrostatic Pressure Analysis — $p = \\rho g h$",
        f"- Depth ($h$): {h:.4f} m",
        f"- Fluid density ($\\rho$): {rho:.2f} kg/m³",
        f"- Gravitational acceleration: {g} m/s²",
        f"- Gauge pressure ($p$): **{p_gauge:.4f} Pa  ({p_gauge / 1000:.4f} kPa)**",
    ]
    if p_sigma > 0:
        steps.append(f"- Pressure uncertainty ($\\pm 1\\sigma$): {p_sigma:.4f} Pa")

    # Contextual annotations
    rq = raw_query.lower()
    if "add more water" in rq or "more water" in rq:
        steps.append("- Adding more water raises $h$, directly increasing pressure ($p \\propto h$).")
    if "vegetable oil" in rq:
        steps.append("- Vegetable oil has lower density than water (~920 kg/m³), so the same depth gives lower pressure.")
    if "bubble" in rq:
        steps.append("- An air bubble expands as it rises because surrounding pressure decreases toward the surface.")

    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_bernoulli(params):
    yield {"type": "step",
           "content": "Applying Bernoulli's equation: $p_1 + \\tfrac{1}{2}\\rho v_1^2 + \\rho g h_1 = p_2 + \\tfrac{1}{2}\\rho v_2^2 + \\rho g h_2$"}

    rho = _safe_float(params.get("rho", WATER_DENSITY), WATER_DENSITY)
    p1  = _safe_float(params.get("p1", 101325.0), 101325.0)
    v1  = _safe_float(params.get("v1", 0.0), 0.0)
    h1  = _safe_float(params.get("h1", 0.0), 0.0)
    h2  = _safe_float(params.get("h2", 0.0), 0.0)
    g   = _safe_float(params.get("g",  9.81),  9.81)

    p2  = params.get("p2")
    v2  = params.get("v2")
    p2  = None if p2 in (None, "") else float(p2)
    v2  = None if v2 in (None, "") else float(v2)

    total_head_1 = p1 / (rho * g) + (v1 ** 2) / (2 * g) + h1
    yield {"type": "step",
           "content": f"Section 1 total head: $H_1 = {p1}/(\\rho g) + v_1^2/(2g) + h_1 = {total_head_1:.4f}$ m"}

    if p2 is None and v2 is not None:
        p2 = rho * g * (total_head_1 - (v2 ** 2) / (2 * g) - h2)
        yield {"type": "step",
               "content": f"$p_2 = \\rho g (H_1 - v_2^2/(2g) - h_2) = {p2:.4f}$ Pa"}
    elif v2 is None and p2 is not None:
        v2_head = total_head_1 - p2 / (rho * g) - h2
        if v2_head < 0:
            yield {"type": "final",
                   "answer": "Error: energy balance gives a negative velocity head — check input pressures/elevations."}
            return
        v2 = np.sqrt(2 * g * v2_head)
        yield {"type": "step",
               "content": f"$v_2 = \\sqrt{{2g(H_1 - p_2/(\\rho g) - h_2)}} = {v2:.4f}$ m/s"}
    elif p2 is None and v2 is None:
        yield {"type": "final",
               "answer": "Bernoulli needs one unknown at section 2 — provide either $p_2$ or $v_2$."}
        return

    total_head_2 = p2 / (rho * g) + (v2 ** 2) / (2 * g) + h2 if (p2 and v2) else None
    yield {
        "type": "final",
        "answer": "\n".join([
            "### Bernoulli Energy Balance",
            f"- $\\rho$ = {rho:.2f} kg/m³",
            f"- Section 1: $p_1 = {p1:.2f}$ Pa,  $v_1 = {v1:.4f}$ m/s,  $z_1 = {h1}$ m",
            f"- Section 1 total head ($H_1$): {total_head_1:.4f} m",
            f"- Section 2: $p_2 = {p2:.4f}$ Pa" if p2 is not None else "",
            f"- Section 2: $v_2 = {v2:.4f}$ m/s" if v2 is not None else "",
            "- Ideal, inviscid, steady flow assumed.",
        ]),
    }


async def solve_flow_meter(params):
    yield {"type": "step", "content": "Evaluating Venturi/Orifice meter using discharge coefficient..."}

    rho = _safe_float(params.get("rho", WATER_DENSITY), WATER_DENSITY)
    d1  = _safe_float(params.get("d1",  0.1),  0.1)
    d2  = _safe_float(params.get("d2",  0.05), 0.05)
    dp  = _safe_float(params.get("dp",  1000.0), 1000.0)   # differential pressure
    Cd  = _safe_float(params.get("cd",  0.98),  0.98)       # discharge coefficient

    if d1 <= 0 or d2 <= 0:
        yield {"type": "final", "answer": "Error: pipe diameters must be positive."}
        return
    if dp < 0:
        yield {"type": "final", "answer": "Error: differential pressure must be non-negative."}
        return

    A1 = np.pi * d1 ** 2 / 4
    A2 = np.pi * d2 ** 2 / 4

    yield {"type": "step",
           "content": f"$A_1 = {A1:.6f}$ m²,  $A_2 = {A2:.6f}$ m²,  $d_2/d_1 = {d2/d1:.4f}$ (beta ratio)"}

    area_ratio = A2 / A1
    denom = 1.0 - area_ratio ** 2
    if abs(denom) < 1e-10:
        yield {"type": "final",
               "answer": "Error: inlet and throat diameters are equal — differential is zero (no measurement possible)."}
        return

    Q  = Cd * A2 * np.sqrt(2 * dp / (rho * denom))
    v1 = Q / A1
    v2 = Q / A2

    yield {"type": "step",
           "content": f"$Q = C_d A_2 \\sqrt{{2\\Delta p / (\\rho(1-(A_2/A_1)^2))}} = {Q:.6f}$ m³/s"}
    yield {"type": "step",
           "content": f"$v_1 = Q/A_1 = {v1:.4f}$ m/s,  $v_2 = Q/A_2 = {v2:.4f}$ m/s"}

    yield {
        "type": "final",
        "answer": "\n".join([
            "### Flow Meter Performance (Venturi / Orifice)",
            f"- Pipe diameter ($d_1$): {d1} m,  Throat diameter ($d_2$): {d2} m",
            f"- Differential pressure ($\\Delta p$): {dp:.2f} Pa",
            f"- Discharge coefficient ($C_d$): {Cd}",
            f"- Volume flow rate ($Q$): **{Q:.6f} m³/s**  ({Q * 1000:.4f} L/s)",
            f"- Inlet velocity ($v_1$): {v1:.4f} m/s",
            f"- Throat velocity ($v_2$): {v2:.4f} m/s",
            f"- Area ratio ($A_2/A_1$): {area_ratio:.4f}",
        ]),
    }


async def solve_pipe_flow(params):
    yield {"type": "step", "content": "Determining flow regime via Reynolds number: $Re = \\rho v D / \\mu$"}

    v   = _safe_float(params.get("v", params.get("velocity", 1.0)), 1.0)
    D   = _safe_float(params.get("D", params.get("d", 0.1)), 0.1)
    rho = _safe_float(params.get("rho", WATER_DENSITY), WATER_DENSITY)
    mu  = _safe_float(params.get("mu", WATER_VISCOSITY), WATER_VISCOSITY)

    if D <= 0:
        yield {"type": "final", "answer": "Error: pipe diameter must be positive."}
        return
    if mu <= 0:
        yield {"type": "final", "answer": "Error: dynamic viscosity must be positive."}
        return

    Re = rho * v * D / mu
    yield {"type": "step",
           "content": f"$Re = \\rho v D / \\mu = {rho} \\times {v} \\times {D} / {mu:.4e} = {Re:.2f}$"}

    if Re < 2300:
        regime = "Laminar"
    elif Re > 4000:
        regime = "Turbulent"
    else:
        regime = "Transitional"

    yield {"type": "step", "content": f"Flow regime: **{regime}** (Re = {Re:.2f})"}

    # Velocity profile across pipe radius
    r_arr = np.linspace(-D / 2, D / 2, 100)
    r_norm = r_arr / (D / 2)   # -1 to +1

    if Re < 2300:
        # Hagen-Poiseuille parabolic: v(r) = 2v_avg * (1 - (r/R)^2)
        v_profile = 2 * v * (1 - r_norm ** 2)
    else:
        # 1/7 power law: v(r) = v_max * (1 - |r/R|)^(1/7)
        # v_max = (8/7) * v_avg  (exact for 1/7 exponent)
        v_max    = (49 / 40) * v   # exact coefficient for n=7 power law
        v_profile = v_max * np.power(np.maximum(0.0, 1 - np.abs(r_norm)), 1.0 / 7.0)

    yield {"type": "diagram", "diagram_type": "velocity_profile",
           "data": [{"r": float(ri), "v": float(vi)} for ri, vi in zip(r_arr, v_profile)]}

    # Friction factor estimate
    if Re < 2300 and Re > 0:
        f_darcy = 64.0 / Re
        f_note  = f"Laminar: $f = 64/Re = {f_darcy:.5f}$"
    elif Re >= 4000:
        # Blasius correlation (smooth pipe, Re < 100 000)
        f_darcy = 0.316 * Re ** (-0.25)
        f_note  = f"Blasius (smooth pipe): $f = 0.316 Re^{{-0.25}} = {f_darcy:.5f}$"
    else:
        f_darcy = None
        f_note  = "Transitional regime — friction factor is indeterminate."

    steps = [
        "### Pipe Flow Diagnostics",
        f"- Mean velocity ($v$): {v:.4f} m/s",
        f"- Pipe diameter ($D$): {D} m",
        f"- Fluid density ($\\rho$): {rho:.2f} kg/m³",
        f"- Dynamic viscosity ($\\mu$): {mu:.4e} Pa·s",
        f"- Reynolds number ($Re$): **{Re:.2f}**",
        f"- Flow regime: **{regime}**",
        f"- Velocity profile: {'Parabolic (Hagen-Poiseuille)' if Re < 2300 else '1/7 Power Law'}",
        f"- Darcy friction factor: {f_note}",
    ]
    if f_darcy:
        steps.append(f"  ($f = {f_darcy:.6f}$)")

    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_head_loss(params):
    yield {"type": "step",
           "content": "Applying Darcy-Weisbach equation: $h_f = f \\dfrac{L}{D} \\dfrac{v^2}{2g}$"}

    L   = _safe_float(params.get("L", params.get("length",   100.0)), 100.0)
    D   = _safe_float(params.get("D", params.get("d",          0.1)),   0.1)
    v   = _safe_float(params.get("v", params.get("velocity",   2.0)),   2.0)
    f   = _safe_float(params.get("f", params.get("friction",  0.02)),  0.02)
    rho = _safe_float(params.get("rho", WATER_DENSITY), WATER_DENSITY)
    g   = _safe_float(params.get("g",  9.81), 9.81)

    if D <= 0:
        yield {"type": "final", "answer": "Error: pipe diameter must be positive."}
        return

    hf = f * (L / D) * (v ** 2 / (2 * g))
    dp = hf * rho * g

    yield {"type": "step",
           "content": f"$h_f = {f} \\times ({L}/{D}) \\times ({v}^2/(2 \\times {g})) = {hf:.4f}$ m"}
    yield {"type": "step",
           "content": f"Pressure drop: $\\Delta p = \\rho g h_f = {rho:.1f} \\times {g} \\times {hf:.4f} = {dp:.4f}$ Pa"}

    # Head loss along pipe length for diagram
    x_arr  = np.linspace(0, L, 100)
    hf_arr = f * (x_arr / D) * (v ** 2 / (2 * g))
    yield {"type": "diagram", "diagram_type": "pressure_curve",
           "data": series_points(x_arr, hf_arr)}

    yield {
        "type": "final",
        "answer": "\n".join([
            "### Major Head Loss — Darcy-Weisbach",
            f"- Pipe length ($L$): {L} m",
            f"- Pipe diameter ($D$): {D} m",
            f"- Mean velocity ($v$): {v} m/s",
            f"- Darcy friction factor ($f$): {f}",
            f"- Head loss ($h_f$): **{hf:.4f} m**",
            f"- Pressure drop ($\\Delta p$): **{dp / 1000:.4f} kPa**",
            f"- Loss gradient ($h_f/L$): {hf / L:.6f} m/m",
        ]),
    }


async def solve_pump_power(params):
    yield {"type": "step",
           "content": "Computing hydraulic power: $P_{hyd} = \\rho g Q H$"}

    rho  = _safe_float(params.get("rho", WATER_DENSITY), WATER_DENSITY)
    g    = _safe_float(params.get("g",   G), G)
    Q    = _safe_float(params.get("Q",   params.get("q",    0.01)), 0.01)
    H    = _safe_float(params.get("H",   params.get("head", 10.0)), 10.0)
    eta  = _safe_float(params.get("eta", params.get("efficiency", 0.75)), 0.75)

    if Q <= 0:
        yield {"type": "final", "answer": "Error: flow rate Q must be positive."}
        return
    if H <= 0:
        yield {"type": "final", "answer": "Error: pump head H must be positive."}
        return
    if not (0 < eta <= 1.0):
        yield {"type": "final",
               "answer": f"Error: efficiency must be between 0 and 1 (got {eta})."}
        return

    P_hyd   = rho * g * Q * H
    P_shaft = P_hyd / eta

    yield {"type": "step",
           "content": f"$P_{{hyd}} = \\rho g Q H = {rho:.1f} \\times {g} \\times {Q} \\times {H} = {P_hyd:.4f}$ W"}
    yield {"type": "step",
           "content": f"$P_{{shaft}} = P_{{hyd}} / \\eta = {P_hyd:.4f} / {eta} = {P_shaft:.4f}$ W"}

    # Power vs flow rate sweep for diagram
    Q_arr = np.linspace(Q * 0.1, Q * 2, 100)
    P_arr = rho * g * Q_arr * H / eta
    yield {"type": "diagram", "diagram_type": "energy_curve",
           "data": series_points(Q_arr, P_arr)}

    yield {
        "type": "final",
        "answer": "\n".join([
            "### Pump Power Analysis",
            f"- Flow rate ($Q$): {Q:.6f} m³/s  ({Q * 1000:.4f} L/s)",
            f"- Pump head ($H$): {H:.4f} m",
            f"- Fluid density ($\\rho$): {rho:.2f} kg/m³",
            f"- Pump efficiency ($\\eta$): {eta * 100:.1f}%",
            f"- Hydraulic power ($P_{{hyd}} = \\rho g Q H$): **{P_hyd:.4f} W  ({P_hyd / 1000:.4f} kW)**",
            f"- Required shaft power ($P_{{shaft}} = P_{{hyd}}/\\eta$): **{P_shaft:.4f} W  ({P_shaft / 1000:.4f} kW)**",
        ]),
    }
