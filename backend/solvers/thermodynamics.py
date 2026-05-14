"""
Thermodynamics Solver
Handles: Ideal Gas, Conduction, Convection, Radiation,
         Calorimetry, Entropy, Thermal Cycles, Polytropic Processes.
"""

import numpy as np
from solvers.utils import normalize_params, validate_physical_params

R_UNIVERSAL = 8.314  # J/(mol·K)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def series_points(x_values, y_values):
    return [{"x": float(x), "y": float(y)} for x, y in zip(x_values, y_values)]


def _safe_float(value, default=0.0):
    try:
        return float(value) if value not in (None, "", "None") else default
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

async def solve_thermo(data):
    yield {"type": "step", "content": "Initializing Advanced Thermal Science Kernel..."}

    params = normalize_params(data.get("parameters", {}))

    is_valid, err = validate_physical_params(params)
    if not is_valid:
        yield {"type": "error", "message": err}
        return

    raw = data.get("raw_query", "").lower()
    pt  = data.get("problem_type", "").lower()

    used_vars = [k for k, v in params.items() if v is not None]
    if used_vars:
        yield {"type": "step", "content": f"Thermal parameters identified: {', '.join(used_vars)}"}

    try:
        if any(kw in pt or kw in raw for kw in ("ideal gas", "pv=nrt", "pv = nrt")):
            async for chunk in solve_ideal_gas(params):
                yield chunk
        elif any(kw in pt or kw in raw for kw in ("radiation", "stefan", "boltzmann", "emissivity")):
            async for chunk in solve_radiation(params):
                yield chunk
        elif any(kw in pt or kw in raw for kw in ("convection", "film", "h_coeff", "newton cooling")):
            async for chunk in solve_convection(params):
                yield chunk
        elif any(kw in pt or kw in raw for kw in ("conduction", "wall", "heat flux", "conductivity", "fourier")):
            async for chunk in solve_conduction(params):
                yield chunk
        elif any(kw in pt or kw in raw for kw in ("entropy", "reversible", "isentropic", "irreversib")):
            async for chunk in solve_entropy(params):
                yield chunk
        elif any(kw in pt or kw in raw for kw in ("cycle", "carnot", "otto", "rankine", "refrigerator", "heat engine")):
            async for chunk in solve_cycles(params):
                yield chunk
        elif any(kw in pt or kw in raw for kw in ("polytropic", "compression", "expansion", "adiabatic", "isothermal")):
            async for chunk in solve_polytropic(params):
                yield chunk
        elif any(kw in pt or kw in raw for kw in ("heat", "specific heat", "calorimetry", "sensible", "temperature change")):
            async for chunk in solve_calorimetry(params):
                yield chunk
        else:
            yield {
                "type": "final",
                "answer": (
                    "I can solve: **Ideal Gas Law**, **Conduction / Convection / Radiation**, "
                    "**Calorimetry**, **Entropy**, **Thermal Cycles** (Carnot, Otto, Rankine), "
                    "and **Polytropic Processes**. Please specify the process type and parameters."
                ),
            }
    except Exception as e:
        yield {"type": "final", "answer": f"Thermo Solver Error: {str(e)}"}


# ---------------------------------------------------------------------------
# Sub-solvers  (each streams genuine calculation steps)
# ---------------------------------------------------------------------------

async def solve_ideal_gas(params):
    """Solve PV = nRT for the single unknown variable."""
    yield {"type": "step", "content": "Applying the Ideal Gas Law: $PV = nRT$"}

    p = params.get("p", params.get("P"))
    v = params.get("v", params.get("V"))
    n = params.get("n")
    t = params.get("t", params.get("T"))
    R = _safe_float(params.get("R", R_UNIVERSAL), R_UNIVERSAL)

    # Normalise to float or None
    p = None if p in (None, "") else float(p)
    v = None if v in (None, "") else float(v)
    n = None if n in (None, "") else float(n)
    t = None if t in (None, "") else float(t)

    yield {"type": "step", "content": f"Gas constant used: $R = {R}$ J/(mol·K)"}
    yield {
        "type": "step",
        "content": (
            f"Known: "
            f"P={'?' if p is None else f'{p:.4g} Pa'}  "
            f"V={'?' if v is None else f'{v:.4g} m³'}  "
            f"n={'?' if n is None else f'{n:.4g} mol'}  "
            f"T={'?' if t is None else f'{t:.4g} K'}"
        ),
    }

    # Solve for the one unknown
    if p is None and None not in (v, n, t):
        yield {"type": "step", "content": r"Rearranging: $P = \frac{nRT}{V}$"}
        p = n * R * t / v
        yield {"type": "step", "content": f"$P = ({n:.4g} \\times {R} \\times {t:.4g}) / {v:.4g}$"}
    elif v is None and None not in (p, n, t):
        yield {"type": "step", "content": r"Rearranging: $V = \frac{nRT}{P}$"}
        v = n * R * t / p
        yield {"type": "step", "content": f"$V = ({n:.4g} \\times {R} \\times {t:.4g}) / {p:.4g}$"}
    elif n is None and None not in (p, v, t):
        yield {"type": "step", "content": r"Rearranging: $n = \frac{PV}{RT}$"}
        n = p * v / (R * t)
        yield {"type": "step", "content": f"$n = ({p:.4g} \\times {v:.4g}) / ({R} \\times {t:.4g})$"}
    elif t is None and None not in (p, v, n):
        yield {"type": "step", "content": r"Rearranging: $T = \frac{PV}{nR}$"}
        t = p * v / (n * R)
        yield {"type": "step", "content": f"$T = ({p:.4g} \\times {v:.4g}) / ({n:.4g} \\times {R})$"}
    else:
        yield {
            "type": "final",
            "answer": "Ideal Gas Law requires exactly **three** known values from $P$, $V$, $n$, $T$.",
        }
        return

    yield {"type": "step", "content": f"Verification: $PV = {p * v:.4f}$ J,  $nRT = {n * R * t:.4f}$ J"}

    # PV diagram for visualisation (isothermal curve)
    v_range = np.linspace(v * 0.2, v * 3, 120)
    p_range = n * R * t / v_range
    yield {"type": "diagram", "diagram_type": "pv_diagram",
           "data": series_points(v_range, p_range / 1000)}  # kPa vs m³

    yield {
        "type": "final",
        "answer": "\n".join([
            "### Ideal Gas Law — $PV = nRT$",
            f"- Pressure ($P$): **{p:.4f} Pa**",
            f"- Volume ($V$): **{v:.6f} m³**",
            f"- Amount ($n$): **{n:.6f} mol**",
            f"- Temperature ($T$): **{t:.4f} K**",
            f"- $PV$ = {p * v:.4f} J  ✓  $nRT$ = {n * R * t:.4f} J",
        ]),
    }


async def solve_radiation(params):
    yield {"type": "step", "content": "Applying Stefan-Boltzmann Law: $Q = \\varepsilon \\sigma A (T_1^4 - T_2^4)$"}

    sigma = 5.670374419e-8   # W/m²·K⁴  (CODATA 2018)
    eps   = _safe_float(params.get("eps",   params.get("emissivity", 1.0)), 1.0)
    A     = _safe_float(params.get("A",     params.get("area",        1.0)), 1.0)
    T1    = _safe_float(params.get("T1",    params.get("t1",         300.0)), 300.0)
    T2    = _safe_float(params.get("T2",    params.get("t2",           0.0)),   0.0)

    yield {"type": "step", "content": f"$\\sigma = {sigma}$ W/m²·K⁴,  $\\varepsilon = {eps}$,  $A = {A}$ m²"}
    yield {"type": "step", "content": f"$T_1^4 = {T1**4:.4e}$ K⁴,  $T_2^4 = {T2**4:.4e}$ K⁴"}
    yield {"type": "step", "content": f"$T_1^4 - T_2^4 = {T1**4 - T2**4:.4e}$ K⁴"}

    Q    = sigma * eps * A * (T1 ** 4 - T2 ** 4)
    flux = Q / A if A else 0.0

    yield {"type": "step", "content": f"$Q = {sigma:.3e} \\times {eps} \\times {A} \\times {T1**4 - T2**4:.3e} = {Q:.4f}$ W"}

    yield {
        "type": "final",
        "answer": "\n".join([
            "### Radiative Heat Transfer",
            f"- Stefan-Boltzmann constant ($\\sigma$): $5.670 \\times 10^{{-8}}$ W/m²·K⁴",
            f"- Emissivity ($\\varepsilon$): {eps}",
            f"- Surface temperature ($T_1$): {T1} K",
            f"- Background temperature ($T_2$): {T2} K",
            f"- Net heat transfer rate ($Q$): **{Q:.4f} W**",
            f"- Radiative heat flux ($q''$): **{flux:.4f} W/m²**",
        ]),
    }


async def solve_convection(params):
    yield {"type": "step", "content": "Applying Newton's Law of Cooling: $Q = hA(T_s - T_\\infty)$"}

    h    = _safe_float(params.get("h",    params.get("h_coeff",    10.0)),  10.0)
    A    = _safe_float(params.get("A",    params.get("area",         1.0)),   1.0)
    Ts   = _safe_float(params.get("Ts",   params.get("t_surface",  350.0)), 350.0)
    Tinf = _safe_float(params.get("Tinf", params.get("t_fluid",    298.0)), 298.0)

    delta_T = Ts - Tinf
    yield {"type": "step", "content": f"$\\Delta T = T_s - T_\\infty = {Ts} - {Tinf} = {delta_T}$ K"}
    yield {"type": "step", "content": f"$Q = {h} \\times {A} \\times {delta_T}$"}

    Q    = h * A * delta_T
    flux = Q / A if A else h * delta_T

    yield {"type": "step", "content": f"$Q = {Q:.4f}$ W,  $q'' = Q/A = {flux:.4f}$ W/m²"}

    yield {
        "type": "final",
        "answer": "\n".join([
            "### Convective Heat Transfer",
            f"- Convection coefficient ($h$): {h} W/m²·K",
            f"- Surface area ($A$): {A} m²",
            f"- $\\Delta T$ (Surface − Fluid): {delta_T} K",
            f"- Total heat rate ($Q$): **{Q:.4f} W**",
            f"- Convective heat flux ($q''$): **{flux:.4f} W/m²**",
        ]),
    }


async def solve_conduction(params):
    yield {"type": "step", "content": "Applying Fourier's Law: $Q = kA\\,\\Delta T / L$"}

    k  = _safe_float(params.get("k",  params.get("conductivity", 0.5)),  0.5)
    L  = _safe_float(params.get("L",  params.get("thickness",   0.05)), 0.05)
    A  = _safe_float(params.get("A",  params.get("area",          1.0)),  1.0)
    T1 = _safe_float(params.get("T1", 373.0), 373.0)
    T2 = _safe_float(params.get("T2", 298.0), 298.0)

    yield {"type": "step", "content": f"$k = {k}$ W/m·K,  $L = {L}$ m,  $A = {A}$ m²"}

    R_th = L / (k * A) if (k * A) else 0.0
    yield {"type": "step", "content": f"Thermal resistance: $R_t = L/(kA) = {L}/({k} \\times {A}) = {R_th:.4e}$ K/W"}

    Q    = (T1 - T2) / R_th if R_th else 0.0
    flux = Q / A if A else (k * (T1 - T2) / L)

    yield {"type": "step", "content": f"$Q = \\Delta T / R_t = ({T1} - {T2}) / {R_th:.4e} = {Q:.4f}$ W"}

    yield {
        "type": "final",
        "answer": "\n".join([
            "### Conductive Heat Transfer (Fourier's Law)",
            f"- Thermal conductivity ($k$): {k} W/m·K",
            f"- Wall thickness ($L$): {L} m",
            f"- Thermal resistance ($R_t$): {R_th:.4e} K/W",
            f"- $T_1 - T_2$: {T1 - T2} K",
            f"- Conduction heat rate ($Q$): **{Q:.4f} W**",
            f"- Heat flux ($q''$): **{flux:.4f} W/m²**",
        ]),
    }


async def solve_calorimetry(params):
    """Sensible heat: Q = mcΔT"""
    yield {"type": "step", "content": "Applying calorimetry relation: $Q = mc\\,\\Delta T$"}

    m  = _safe_float(params.get("m",  params.get("mass",       1.0)),    1.0)
    c  = _safe_float(params.get("c",  params.get("sp_heat", 4186.0)), 4186.0)
    dt = _safe_float(params.get("dt", params.get("delta_t",   10.0)),   10.0)

    yield {"type": "step", "content": f"$m = {m}$ kg,  $c = {c}$ J/(kg·K),  $\\Delta T = {dt}$ K"}

    Q = m * c * dt
    yield {"type": "step", "content": f"$Q = {m} \\times {c} \\times {dt} = {Q:.4f}$ J"}

    yield {
        "type": "final",
        "answer": "\n".join([
            "### Calorimetry — $Q = mc\\Delta T$",
            f"- Mass ($m$): {m:.4f} kg",
            f"- Specific heat ($c$): {c:.4f} J/(kg·K)",
            f"- Temperature change ($\\Delta T$): {dt:.4f} K",
            f"- Heat energy ($Q$): **{Q:.4f} J**",
        ]),
    }


async def solve_entropy(params):
    yield {"type": "step", "content": "Evaluating entropy change: $\\Delta S = Q/T$ (reversible process)"}

    q  = _safe_float(params.get("q",  0.0))
    t  = _safe_float(params.get("t",  params.get("T", 298.15)), 298.15)
    cp = params.get("cp")
    t1 = params.get("t1", params.get("T1"))
    t2 = params.get("t2", params.get("T2"))

    yield {"type": "step", "content": f"$Q = {q}$ J,  $T_{{ref}} = {t}$ K"}

    ds = q / t if t else 0.0
    yield {"type": "step", "content": f"$\\Delta S_{{Q/T}} = {q}/{t} = {ds:.6f}$ J/K"}

    steps = [
        "### Entropy Analysis",
        f"- Heat interaction ($Q$): {q:.4f} J",
        f"- Reference temperature ($T$): {t:.4f} K",
        f"- Entropy change from $Q/T$: **{ds:.6f} J/K**",
    ]

    if all(x not in (None, "") for x in (cp, t1, t2)):
        cp_f = float(cp)
        t1_f = float(t1)
        t2_f = float(t2)
        if t1_f > 0 and t2_f > 0:
            yield {"type": "step",
                   "content": f"Temperature-dependent entropy: $\\Delta S = c_p \\ln(T_2/T_1)$"}
            yield {"type": "step",
                   "content": f"$\\Delta S = {cp_f} \\times \\ln({t2_f}/{t1_f}) = {cp_f * np.log(t2_f / t1_f):.6f}$ J/(kg·K)"}
            ds_temp = cp_f * np.log(t2_f / t1_f)
            steps.append(f"- Entropy change from $c_p\\ln(T_2/T_1)$: **{ds_temp:.6f} J/(kg·K)**")

    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_cycles(params):
    yield {"type": "step", "content": "Computing thermal cycle performance limits..."}

    th  = _safe_float(params.get("th", params.get("t_high", 500.0)), 500.0)
    tl  = _safe_float(params.get("tl", params.get("t_low",  300.0)), 300.0)

    yield {"type": "step", "content": f"Hot reservoir $T_H = {th}$ K,  Cold reservoir $T_L = {tl}$ K"}

    if th <= tl:
        yield {"type": "final",
               "answer": "Error: hot reservoir temperature must exceed cold reservoir temperature."}
        return

    efficiency = 1.0 - (tl / th)
    cop_refrig = tl / (th - tl)
    cop_hp     = th / (th - tl)

    yield {"type": "step", "content": f"Carnot efficiency: $\\eta = 1 - T_L/T_H = 1 - {tl}/{th} = {efficiency:.6f}$"}
    yield {"type": "step", "content": f"COP (refrigerator): $T_L/(T_H - T_L) = {tl}/{th - tl:.2f} = {cop_refrig:.6f}$"}
    yield {"type": "step", "content": f"COP (heat pump): $T_H/(T_H - T_L) = {th}/{th - tl:.2f} = {cop_hp:.6f}$"}

    # T-S diagram approximation (rectangle for Carnot)
    x = np.array([0, 1, 1, 0, 0])
    y = np.array([tl, tl, th, th, tl])
    yield {"type": "diagram", "diagram_type": "ts_diagram",
           "data": series_points(x, y)}

    yield {
        "type": "final",
        "answer": "\n".join([
            "### Carnot Cycle Performance",
            f"- Hot reservoir ($T_H$): {th:.4f} K",
            f"- Cold reservoir ($T_L$): {tl:.4f} K",
            f"- Carnot efficiency ($\\eta$): **{efficiency:.6f}** ({efficiency * 100:.2f} %)",
            f"- COP — Refrigerator: **{cop_refrig:.6f}**",
            f"- COP — Heat Pump: **{cop_hp:.6f}**",
        ]),
    }


async def solve_polytropic(params):
    yield {"type": "step", "content": "Evaluating polytropic process: $pV^n = \\text{const}$"}

    p1 = _safe_float(params.get("p1", 101325.0), 101325.0)
    v1 = _safe_float(params.get("v1", 1.0),          1.0)
    p2 = _safe_float(params.get("p2", 202650.0), 202650.0)
    n  = _safe_float(params.get("n_poly", params.get("n", 1.3)), 1.3)

    yield {"type": "step", "content": f"$p_1 = {p1:.3f}$ Pa,  $V_1 = {v1:.6f}$ m³,  $p_2 = {p2:.3f}$ Pa,  $n = {n}$"}

    v2 = v1 * (p1 / p2) ** (1.0 / n) if p2 else v1
    yield {"type": "step", "content": f"$V_2 = V_1 (p_1/p_2)^{{1/n}} = {v1:.4f} \\times ({p1:.0f}/{p2:.0f})^{{1/{n}}} = {v2:.6f}$ m³"}

    if abs(1.0 - n) > 1e-9:
        work = (p2 * v2 - p1 * v1) / (1.0 - n)
        yield {"type": "step",
               "content": f"$W = (p_2 V_2 - p_1 V_1)/(1-n) = ({p2:.2f}\\times{v2:.4f} - {p1:.2f}\\times{v1:.4f})/{1-n:.4f} = {work:.4f}$ J"}
    else:
        work = p1 * v1 * np.log(v2 / v1)   # isothermal
        yield {"type": "step",
               "content": f"Isothermal ($n=1$): $W = p_1 V_1 \\ln(V_2/V_1) = {work:.4f}$ J"}

    # PV path diagram
    v_path = np.linspace(min(v1, v2), max(v1, v2), 120)
    c_val  = p1 * (v1 ** n)
    p_path = c_val / (v_path ** n)
    yield {"type": "diagram", "diagram_type": "pv_diagram",
           "data": series_points(v_path, p_path / 1000)}   # kPa vs m³

    yield {
        "type": "final",
        "answer": "\n".join([
            "### Polytropic Process Analysis ($pV^n = C$)",
            f"- Polytropic index ($n$): {n:.4f}",
            f"- Initial state: $p_1 = {p1:.3f}$ Pa,  $V_1 = {v1:.6f}$ m³",
            f"- Final state:   $p_2 = {p2:.3f}$ Pa,  $V_2 = {v2:.6f}$ m³",
            f"- Boundary work ($W$): **{work:.4f} J**",
            *(["*(n=1: isothermal process)*"] if abs(n - 1) < 1e-9 else []),
            *(["*(n=γ: isentropic/adiabatic process)*"] if abs(n - 1.4) < 0.05 else []),
        ]),
    }
