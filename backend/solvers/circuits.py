"""
Circuit Analysis Solver
Handles: Ohm's Law, Resistor Networks (series/parallel),
         RC / RL / RLC transients, AC impedance & phasors,
         resonance, power factor, basic nodal analysis.
"""

import numpy as np
import cmath

from solvers.utils import normalize_params, validate_physical_params


def _safe_float(value, default=0.0):
    try:
        return float(value) if value not in (None, "", "None") else default
    except (TypeError, ValueError):
        return default


def series_points(x_values, y_values):
    return [{"x": float(x), "y": float(y)} for x, y in zip(x_values, y_values)]


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

async def solve_circuits(data):
    yield {"type": "step", "content": "Initializing Circuit Analysis Kernel..."}

    params = normalize_params(data.get("parameters", {}))

    is_valid, err = validate_physical_params(params)
    if not is_valid:
        yield {"type": "error", "message": err}
        return

    raw = data.get("raw_query", "").lower()

    used_vars = [k for k, v in params.items() if v is not None]
    if used_vars:
        yield {"type": "step", "content": f"Components detected: {', '.join(used_vars)}"}

    try:
        if any(kw in raw for kw in ("ac", "impedance", "phasor", "rlc", "reactance")):
            async for chunk in solve_ac_impedance(params):
                yield chunk
        elif any(kw in raw for kw in ("resonan", "resonance", "lc")):
            async for chunk in solve_resonance(params):
                yield chunk
        elif any(kw in raw for kw in ("power factor", "apparent", "reactive power", "real power")):
            async for chunk in solve_power_factor(params):
                yield chunk
        elif any(kw in raw for kw in ("series", "parallel", "network", "resistor")):
            async for chunk in solve_resistor_network(params):
                yield chunk
        elif any(kw in raw for kw in ("rc circuit", "rc transient", "capacitor charge")):
            async for chunk in solve_rc_circuit(params):
                yield chunk
        elif any(kw in raw for kw in ("rl circuit", "rl transient", "inductor")):
            async for chunk in solve_rl_circuit(params):
                yield chunk
        elif any(kw in raw for kw in ("ohm", "v=ir", "voltage", "current", "resistance")):
            async for chunk in solve_ohms_law(params):
                yield chunk
        else:
            yield {"type": "step", "content": "Applying Kirchhoff's Laws (KVL / KCL)..."}
            yield {
                "type": "final",
                "answer": (
                    "I can solve: **Ohm's Law**, **Series/Parallel Resistor Networks**, "
                    "**RC / RL Transients**, **AC Impedance (RLC)**, **Resonance**, and **Power Factor**. "
                    "Please specify the circuit type and component values."
                ),
            }
    except Exception as e:
        yield {"type": "final", "answer": f"Circuit Solver Error: {str(e)}"}


# ---------------------------------------------------------------------------
# Sub-solvers
# ---------------------------------------------------------------------------

async def solve_ohms_law(params):
    yield {"type": "step", "content": "Applying Ohm's Law: $V = IR$"}

    # Use None sentinel so we can distinguish 'not provided' from 0
    v = params.get("v", params.get("voltage"))
    i = params.get("i", params.get("current"))
    r = params.get("r", params.get("resistance"))

    v = None if v in (None, "") else float(v)
    i = None if i in (None, "") else float(i)
    r = None if r in (None, "") else float(r)

    known = sum(x is not None for x in (v, i, r))
    if known < 2:
        yield {"type": "final",
               "answer": "Ohm's Law requires at least **two** of: $V$ (voltage), $I$ (current), $R$ (resistance)."}
        return

    steps = ["### Ohm's Law Resolution"]

    if v is None:
        v = i * r
        yield {"type": "step", "content": f"$V = IR = {i} \\times {r} = {v:.4f}$ V"}
        steps.append(f"- Calculated voltage: $V = IR = {v:.4f}$ V")
    elif i is None:
        if r == 0:
            yield {"type": "final", "answer": "Error: resistance is zero — current would be infinite (short circuit)."}
            return
        i = v / r
        yield {"type": "step", "content": f"$I = V/R = {v}/{r} = {i:.6f}$ A"}
        steps.append(f"- Calculated current: $I = V/R = {i:.6f}$ A")
    elif r is None:
        if i == 0:
            yield {"type": "final", "answer": "Error: current is zero — resistance is undefined (open circuit)."}
            return
        r = v / i
        yield {"type": "step", "content": f"$R = V/I = {v}/{i} = {r:.4f}$ Ω"}
        steps.append(f"- Calculated resistance: $R = V/I = {r:.4f}$ Ω")

    power = v * i
    yield {"type": "step", "content": f"Power: $P = VI = {v:.4f} \\times {i:.6f} = {power:.4f}$ W"}
    steps += [
        f"- Voltage ($V$): {v:.4f} V",
        f"- Current ($I$): {i:.6f} A",
        f"- Resistance ($R$): {r:.4f} Ω",
        f"- Power ($P = VI$): **{power:.4f} W**",
    ]

    yield {
        "type": "diagram",
        "diagram_type": "circuit_ohms",
        "data": {"voltage": v, "current": i, "resistance": r, "power": power},
    }
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_resistor_network(params):
    yield {"type": "step", "content": "Analyzing resistor network topology..."}

    raw_resistors = params.get("resistors", [])
    mode          = str(params.get("mode", "series")).lower().strip()

    if mode not in ("series", "parallel"):
        yield {"type": "final",
               "answer": f"Unknown network mode '{mode}'. Use **'series'** or **'parallel'**."}
        return

    # Coerce list items to float, skip invalid
    resistors = []
    for item in raw_resistors:
        try:
            val = float(item)
            if val < 0:
                yield {"type": "final", "answer": f"Error: negative resistance {val} Ω is not physical."}
                return
            resistors.append(val)
        except (TypeError, ValueError):
            pass  # skip non-numeric entries

    if not resistors:
        yield {"type": "final",
               "answer": "No valid resistor values found. Provide a list, e.g. `resistors: [100, 220, 470]`."}
        return

    yield {"type": "step", "content": f"Mode: **{mode.capitalize()}**,  values: {resistors} Ω"}

    if mode == "series":
        req = sum(resistors)
        yield {"type": "step",
               "content": f"$R_{{eq}} = {' + '.join(str(r) for r in resistors)} = {req:.4f}$ Ω"}
    else:
        # Guard against any zero — parallel with a short = 0 Ω
        if any(r == 0 for r in resistors):
            yield {"type": "final",
                   "answer": "Error: one or more resistors is 0 Ω — parallel combination is a short circuit (0 Ω)."}
            return
        conductances = [1.0 / r for r in resistors]
        req = 1.0 / sum(conductances)
        cond_str = " + ".join(f"1/{r}" for r in resistors)
        yield {"type": "step",
               "content": f"$1/R_{{eq}} = {cond_str}$  →  $R_{{eq}} = {req:.4f}$ Ω"}

    v_supply = _safe_float(params.get("v", params.get("voltage")), 0.0)
    extra = []
    if v_supply and req > 0:
        i_total = v_supply / req
        p_total = v_supply * i_total
        yield {"type": "step",
               "content": f"$I_{{total}} = V/R_{{eq}} = {v_supply}/{req:.4f} = {i_total:.4f}$ A"}
        extra = [
            f"- Supply voltage ($V$): {v_supply} V",
            f"- Total current ($I$): {i_total:.4f} A",
            f"- Total power ($P$): {p_total:.4f} W",
        ]

    yield {
        "type": "diagram",
        "diagram_type": "resistor_network",
        "data": {"resistors": resistors, "mode": mode, "equivalent": req},
    }
    yield {
        "type": "final",
        "answer": "\n".join([
            f"### {mode.capitalize()} Resistor Network",
            f"- Components: {resistors} Ω",
            f"- Equivalent resistance ($R_{{eq}}$): **{req:.4f} Ω**",
            *extra,
        ]),
    }


async def solve_rc_circuit(params):
    yield {"type": "step", "content": "Analyzing RC transient response: $v_C(t) = V_0(1 - e^{-t/\\tau})$"}

    R   = _safe_float(params.get("r", params.get("resistance", 1000)), 1000.0)
    C   = _safe_float(params.get("c", params.get("capacitance", 1e-6)), 1e-6)
    V0  = _safe_float(params.get("v", params.get("voltage", 5.0)), 5.0)

    if R <= 0 or C <= 0:
        yield {"type": "final", "answer": "Error: R and C must both be positive."}
        return

    tau = R * C
    yield {"type": "step", "content": f"$\\tau = RC = {R} \\times {C:.2e} = {tau * 1000:.4f}$ ms"}
    yield {"type": "step", "content": f"63.2% charge at $t = \\tau = {tau * 1000:.4f}$ ms"}
    yield {"type": "step", "content": f"99% settled at $t = 5\\tau = {5 * tau * 1000:.4f}$ ms"}

    t_arr = np.linspace(0, 6 * tau, 300)
    vc    = V0 * (1 - np.exp(-t_arr / tau))
    ic    = (V0 / R) * np.exp(-t_arr / tau)

    yield {"type": "diagram", "diagram_type": "time_series",
           "data": series_points(t_arr * 1000, vc)}   # t in ms, v in V

    yield {
        "type": "final",
        "answer": "\n".join([
            "### RC Circuit — Charging Transient",
            f"- Resistance ($R$): {R} Ω",
            f"- Capacitance ($C$): {C * 1e6:.3f} μF",
            f"- Supply voltage ($V_0$): {V0} V",
            f"- Time constant ($\\tau = RC$): **{tau * 1000:.4f} ms**",
            f"- 5τ settling time (99%): **{5 * tau * 1000:.4f} ms**",
            f"- Initial current ($I_0 = V_0/R$): {V0 / R * 1000:.4f} mA",
        ]),
    }


async def solve_rl_circuit(params):
    yield {"type": "step", "content": "Analyzing RL transient response: $i_L(t) = I_f(1 - e^{-t/\\tau})$"}

    R  = _safe_float(params.get("r", params.get("resistance", 100)), 100.0)
    L  = _safe_float(params.get("l", params.get("inductance", 0.1)), 0.1)
    V0 = _safe_float(params.get("v", params.get("voltage", 10.0)), 10.0)

    if R <= 0 or L <= 0:
        yield {"type": "final", "answer": "Error: R and L must both be positive."}
        return

    tau    = L / R
    I_final = V0 / R

    yield {"type": "step", "content": f"$\\tau = L/R = {L}/{R} = {tau * 1000:.4f}$ ms"}
    yield {"type": "step",
           "content": f"Final current: $I_f = V_0/R = {V0}/{R} = {I_final:.4f}$ A"}

    t_arr = np.linspace(0, 6 * tau, 300)
    i_L   = I_final * (1 - np.exp(-t_arr / tau))
    v_L   = V0 * np.exp(-t_arr / tau)

    yield {"type": "diagram", "diagram_type": "time_series",
           "data": series_points(t_arr * 1000, i_L)}

    yield {
        "type": "final",
        "answer": "\n".join([
            "### RL Circuit — Current Build-up Transient",
            f"- Resistance ($R$): {R} Ω",
            f"- Inductance ($L$): {L * 1000:.3f} mH",
            f"- Supply voltage ($V_0$): {V0} V",
            f"- Time constant ($\\tau = L/R$): **{tau * 1000:.4f} ms**",
            f"- Final (steady-state) current: **{I_final:.4f} A**",
            f"- 5τ settling time (99%): **{5 * tau * 1000:.4f} ms**",
        ]),
    }


async def solve_ac_impedance(params):
    yield {"type": "step", "content": "Computing complex AC impedance for RLC series circuit..."}

    f = _safe_float(params.get("f", params.get("frequency", 60.0)), 60.0)
    R = _safe_float(params.get("r", params.get("resistance", 0.0)), 0.0)
    L = _safe_float(params.get("l", params.get("inductance", 0.0)), 0.0)
    C = _safe_float(params.get("c", params.get("capacitance", 0.0)), 0.0)

    if f <= 0:
        yield {"type": "final", "answer": "Error: frequency must be positive."}
        return

    w = 2 * np.pi * f
    yield {"type": "step", "content": f"$\\omega = 2\\pi f = 2\\pi \\times {f} = {w:.4f}$ rad/s"}

    Z_R = complex(R, 0)
    Z_L = complex(0, w * L)           if L > 0 else complex(0, 0)
    Z_C = complex(0, -1.0 / (w * C)) if C > 0 else complex(0, 0)

    if L > 0:
        yield {"type": "step",
               "content": f"$Z_L = j\\omega L = j \\times {w:.4f} \\times {L} = j{Z_L.imag:.4f}$ Ω"}
    if C > 0:
        yield {"type": "step",
               "content": f"$Z_C = 1/(j\\omega C) = -j/{w:.4f}\\times{C:.2e} = j{Z_C.imag:.4f}$ Ω"}

    Z_total = Z_R + Z_L + Z_C
    mag     = abs(Z_total)
    phase   = np.degrees(cmath.phase(Z_total))

    yield {"type": "step",
           "content": f"$Z = Z_R + Z_L + Z_C = {Z_total.real:.4f} + j{Z_total.imag:.4f}$ Ω"}
    yield {"type": "step",
           "content": f"$|Z| = \\sqrt{{R^2+(X_L-X_C)^2}} = {mag:.4f}$ Ω,  $\\angle Z = {phase:.2f}°$"}

    # Phasor diagram data
    yield {
        "type": "diagram",
        "diagram_type": "phasor",
        "data": {
            "R": R, "X_L": Z_L.imag, "X_C": Z_C.imag,
            "Z_mag": mag, "Z_phase": phase,
            "frequency": f,
        },
    }

    # Optional: voltage / current if supply given
    extra = []
    V_s = _safe_float(params.get("v", params.get("voltage")), 0.0)
    if V_s and mag > 0:
        I_mag = V_s / mag
        yield {"type": "step",
               "content": f"$I = V/|Z| = {V_s}/{mag:.4f} = {I_mag:.4f}$ A at phase ${-phase:.2f}°$"}
        extra = [
            f"- Supply voltage ($V_s$): {V_s} V",
            f"- Current magnitude ($I$): {I_mag:.4f} A",
            f"- Current phase: {-phase:.2f}°",
        ]

    yield {
        "type": "final",
        "answer": "\n".join([
            "### AC Impedance Analysis — RLC Series",
            f"- Frequency ($f$): {f} Hz  ($\\omega = {w:.4f}$ rad/s)",
            f"- $R$: {R} Ω,  $X_L = \\omega L$: {Z_L.imag:.4f} Ω,  $X_C = -1/(\\omega C)$: {Z_C.imag:.4f} Ω",
            "#### Total Impedance",
            f"- Rectangular: $Z = {Z_total.real:.4f} + j{Z_total.imag:.4f}$ Ω",
            f"- Polar: $|Z| = {mag:.4f}$ Ω,  $\\angle Z = {phase:.2f}°$",
            *extra,
        ]),
    }


async def solve_resonance(params):
    yield {"type": "step", "content": "Computing LC resonance frequency..."}

    L = _safe_float(params.get("l", params.get("inductance", 0.0)), 0.0)
    C = _safe_float(params.get("c", params.get("capacitance", 0.0)), 0.0)
    R = _safe_float(params.get("r", params.get("resistance", 0.0)), 0.0)

    if L <= 0 or C <= 0:
        yield {"type": "final",
               "answer": "Resonance requires positive values for both **L** (inductance) and **C** (capacitance)."}
        return

    w0 = 1.0 / np.sqrt(L * C)
    f0 = w0 / (2 * np.pi)

    yield {"type": "step",
           "content": f"$\\omega_0 = 1/\\sqrt{{LC}} = 1/\\sqrt{{{L}\\times{C:.2e}}} = {w0:.4f}$ rad/s"}
    yield {"type": "step", "content": f"$f_0 = \\omega_0/(2\\pi) = {f0:.4f}$ Hz"}

    extra = []
    if R > 0:
        Q  = (1.0 / R) * np.sqrt(L / C)
        BW = f0 / Q
        yield {"type": "step",
               "content": f"$Q = (1/R)\\sqrt{{L/C}} = {Q:.4f}$,  Bandwidth $= f_0/Q = {BW:.4f}$ Hz"}
        extra = [
            f"- Quality factor ($Q$): **{Q:.4f}**",
            f"- Bandwidth ($BW = f_0/Q$): **{BW:.4f} Hz**",
            f"- Lower −3 dB: {f0 - BW / 2:.4f} Hz",
            f"- Upper −3 dB: {f0 + BW / 2:.4f} Hz",
        ]

    # Impedance vs frequency sweep for diagram
    w_arr = np.logspace(np.log10(w0 / 10), np.log10(w0 * 10), 300)
    Z_arr = np.array([
        abs(complex(R, w * L - 1.0 / (w * C))) for w in w_arr
    ])
    yield {"type": "diagram", "diagram_type": "frequency_sweep",
           "data": series_points((w_arr / (2 * np.pi)), Z_arr)}

    yield {
        "type": "final",
        "answer": "\n".join([
            "### LC Resonance Analysis",
            f"- Inductance ($L$): {L * 1000:.4f} mH",
            f"- Capacitance ($C$): {C * 1e6:.4f} μF",
            f"- Resonant angular frequency ($\\omega_0$): **{w0:.4f} rad/s**",
            f"- Resonant frequency ($f_0$): **{f0:.4f} Hz**",
            *extra,
        ]),
    }


async def solve_power_factor(params):
    yield {"type": "step", "content": "Computing AC power quantities from impedance angle..."}

    V_rms = _safe_float(params.get("v", params.get("voltage",  230.0)), 230.0)
    I_rms = _safe_float(params.get("i", params.get("current",    0.0)),   0.0)
    phi   = _safe_float(params.get("phi", params.get("angle",   0.0)),    0.0)   # degrees
    pf    = _safe_float(params.get("pf",  params.get("power_factor", 0.0)), 0.0)

    # Derive PF from angle if not given
    if pf == 0.0 and phi != 0.0:
        pf = np.cos(np.radians(phi))
    elif phi == 0.0 and pf != 0.0:
        phi = np.degrees(np.arccos(np.clip(pf, -1, 1)))

    # Derive current from other params if missing
    R = _safe_float(params.get("r", params.get("resistance", 0.0)), 0.0)
    Z = _safe_float(params.get("z", params.get("impedance",  0.0)), 0.0)
    if I_rms == 0.0:
        if Z > 0:
            I_rms = V_rms / Z
        elif R > 0 and pf > 0:
            Z_calc = R / pf
            I_rms  = V_rms / Z_calc

    if I_rms == 0.0:
        yield {"type": "final",
               "answer": "Power factor analysis needs current ($I$) or impedance ($Z$) in addition to voltage."}
        return

    S = V_rms * I_rms                    # apparent power (VA)
    P = S * pf                           # real power (W)
    Q = S * np.sin(np.radians(phi))      # reactive power (VAR)

    yield {"type": "step",
           "content": f"Power factor angle: $\\phi = {phi:.2f}°$,  $\\cos\\phi = {pf:.4f}$"}
    yield {"type": "step", "content": f"Apparent power: $S = V_{{rms}} I_{{rms}} = {V_rms}\\times{I_rms:.4f} = {S:.4f}$ VA"}
    yield {"type": "step", "content": f"Real power: $P = S\\cos\\phi = {P:.4f}$ W"}
    yield {"type": "step", "content": f"Reactive power: $Q = S\\sin\\phi = {Q:.4f}$ VAR"}

    yield {
        "type": "final",
        "answer": "\n".join([
            "### AC Power Factor Analysis",
            f"- $V_{{rms}}$: {V_rms} V,  $I_{{rms}}$: {I_rms:.4f} A",
            f"- Power factor ($\\cos\\phi$): **{pf:.4f}**  ($\\phi = {phi:.2f}°$)",
            f"- Apparent power ($S$): {S:.4f} VA",
            f"- Real (active) power ($P$): **{P:.4f} W**",
            f"- Reactive power ($Q$): {Q:.4f} VAR",
            f"- {'Lagging (inductive)' if phi > 0 else 'Leading (capacitive)' if phi < 0 else 'Unity'} power factor",
        ]),
        }
