"""
Universal Physics Solver
Handles: kinematics, optics (Snell's Law / total internal reflection),
         wave mechanics, Doppler effect.
"""

import asyncio
import numpy as np
from solvers.utils import normalize_params, validate_physical_params


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value, default=0.0):
    try:
        return float(value) if value not in (None, "", "None") else default
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

async def solve_physics(data):
    yield {"type": "step", "content": "Initializing Universal Physics Kernel..."}

    params = normalize_params(data.get("parameters", {}))

    is_valid, err = validate_physical_params(params)
    if not is_valid:
        yield {"type": "error", "message": err}
        return

    raw = data.get("raw_query", "").lower()

    used_vars = [k for k, v in params.items() if v is not None]
    if used_vars:
        yield {"type": "step",
               "content": f"Physics variables detected: {', '.join(used_vars)}"}

    try:
        if any(kw in raw for kw in ("snell", "refraction", "optical", "optic")):
            async for chunk in solve_optics(params):
                yield chunk

        elif "doppler" in raw:
            async for chunk in solve_doppler(params):
                yield chunk

        elif any(kw in raw for kw in ("wave", "frequency", "wavelength", "lambda")):
            async for chunk in solve_waves(params):
                yield chunk

        elif any(kw in raw for kw in ("motion", "kinematics", "vel", "accel",
                                       "suvat", "displacement")):
            async for chunk in solve_kinematics(params):
                yield chunk

        else:
            yield {"type": "step",
                   "content": "Applying General Physics Principles..."}
            yield {"type": "final",
                   "answer": (
                       "Analysis complete. Please provide specific parameters for "
                       "Optics, Waves, Doppler, or Kinematics."
                   )}

    except Exception as exc:
        yield {"type": "final", "answer": f"Physics Solver Error: {exc}"}


# ---------------------------------------------------------------------------
# Sub-solvers
# ---------------------------------------------------------------------------

async def solve_optics(params):
    yield {"type": "step", "content": "Calculating Optical Refraction via Snell's Law..."}

    n1        = _safe_float(params.get("n1", 1.0))
    theta1    = _safe_float(params.get("theta1", params.get("theta", 30.0)))
    n2        = _safe_float(params.get("n2", 1.5))

    if n1 <= 0 or n2 <= 0:
        yield {"type": "final",
               "answer": "Error: refractive indices must be positive."}
        return
    if not (0 <= theta1 <= 90):
        yield {"type": "final",
               "answer": "Error: incidence angle must be between 0° and 90°."}
        return

    sin_theta2 = (n1 * np.sin(np.radians(theta1))) / n2

    # Critical angle (when going from denser → less dense medium)
    if n1 > n2:
        theta_c = np.degrees(np.arcsin(n2 / n1))
        tir_note = (f"\n- **Critical angle** ($\\theta_c = \\arcsin(n_2/n_1)$): "
                    f"{theta_c:.4f}°")
    else:
        theta_c  = None
        tir_note = ""

    steps = ["### Optics Analysis — Snell's Law",
             f"- Medium 1 ($n_1$): {n1}",
             f"- Incidence angle ($\\theta_1$): {theta1}°",
             f"- Medium 2 ($n_2$): {n2}"]

    if abs(sin_theta2) <= 1.0:
        theta2 = np.degrees(np.arcsin(sin_theta2))

        # Optional uncertainty propagation
        uncertainties = {k.replace("_sigma", ""): _safe_float(v)
                         for k, v in params.items() if k.endswith("_sigma")}
        theta2_sigma = 0.0
        if uncertainties:
            try:
                from solvers.utils import propagate_uncertainty
                expr   = "asin((n1 * sin(theta1 * pi / 180)) / n2) * 180 / pi"
                p_eval = {"n1": n1, "theta1": theta1, "n2": n2, "pi": np.pi}
                theta2_sigma = propagate_uncertainty(expr, p_eval, uncertainties)
            except Exception:
                pass

        steps.append(f"**Refraction angle ($\\theta_2$):** {theta2:.4f}°")
        if theta2_sigma > 0:
            steps.append(f"  - Uncertainty ($\\pm 1\\sigma$): ±{theta2_sigma:.4f}°")
        steps.append(tir_note)

        # Fresnel reflectance (s-polarization) as bonus
        cos1 = np.cos(np.radians(theta1))
        cos2 = np.cos(np.radians(theta2))
        Rs   = ((n1 * cos1 - n2 * cos2) / (n1 * cos1 + n2 * cos2)) ** 2
        Rp   = ((n1 * cos2 - n2 * cos1) / (n1 * cos2 + n2 * cos1)) ** 2
        R    = 0.5 * (Rs + Rp)
        steps.append(f"- Fresnel reflectance (unpolarised): {R * 100:.2f}%")

    else:
        steps.append("**Total Internal Reflection occurs** — no transmitted ray.")
        steps.append(tir_note)

    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_waves(params):
    yield {"type": "step", "content": "Analyzing Wave Characteristics..."}

    v   = _safe_float(params.get("v",          343.0))   # speed of sound default
    f   = _safe_float(params.get("f",          params.get("frequency",  0.0)))
    lam = _safe_float(params.get("lambda",     params.get("wavelength", 0.0)))
    T   = _safe_float(params.get("T",          params.get("period",     0.0)))

    steps = ["### Wave Mechanics"]

    # Resolve missing quantities
    if f > 0 and lam == 0:
        lam = v / f
        T   = 1 / f
        steps.append(f"- Wave speed ($v$): {v:.4f} m/s")
        steps.append(f"- Frequency ($f$): {f:.4f} Hz")
        steps.append(f"- Wavelength ($\\lambda = v/f$): **{lam:.6f} m**")
        steps.append(f"- Period ($T = 1/f$): {T:.6f} s")

    elif lam > 0 and f == 0:
        f = v / lam
        T = 1 / f
        steps.append(f"- Wave speed ($v$): {v:.4f} m/s")
        steps.append(f"- Wavelength ($\\lambda$): {lam:.6f} m")
        steps.append(f"- Frequency ($f = v/\\lambda$): **{f:.4f} Hz**")
        steps.append(f"- Period ($T = 1/f$): {T:.6f} s")

    elif T > 0 and f == 0:
        f   = 1 / T
        lam = v / f
        steps.append(f"- Wave speed ($v$): {v:.4f} m/s")
        steps.append(f"- Period ($T$): {T:.6f} s")
        steps.append(f"- Frequency ($f = 1/T$): **{f:.4f} Hz**")
        steps.append(f"- Wavelength ($\\lambda = v/f$): {lam:.6f} m")

    elif f > 0 and lam > 0:
        v_calc = f * lam
        steps.append(f"- Frequency ($f$): {f:.4f} Hz")
        steps.append(f"- Wavelength ($\\lambda$): {lam:.6f} m")
        steps.append(f"- Derived wave speed ($v = f\\lambda$): **{v_calc:.4f} m/s**")

    else:
        steps.append("Please provide at least two of: wave speed, frequency, wavelength, or period.")

    steps.extend([
        "",
        "#### Wave Relation",
        r"$v = f \lambda \quad;\quad T = \frac{1}{f}$",
    ])
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_doppler(params):
    yield {"type": "step", "content": "Executing Doppler Effect Analysis..."}

    fs = _safe_float(params.get("fs", params.get("f_source", 440.0)))
    v  = _safe_float(params.get("v",  343.0))                # medium speed
    vs = _safe_float(params.get("vs", params.get("v_source",   0.0)))  # source vel (+away)
    vo = _safe_float(params.get("vo", params.get("v_observer", 0.0)))  # observer vel (+toward)

    if v <= 0:
        yield {"type": "final",
               "answer": "Error: wave speed in medium must be positive."}
        return
    if abs(vs) >= v:
        yield {"type": "final",
               "answer": "Error: source speed must be less than wave speed (subsonic regime)."}
        return

    # Standard Doppler formula: f_obs = fs * (v + v_o) / (v + v_s)
    # Convention: v_s > 0 → source moving away; v_o > 0 → observer moving toward
    f_obs  = fs * (v + vo) / (v + vs)
    delta  = f_obs - fs
    shift  = "blue-shift (higher pitch)" if delta > 0 else ("red-shift (lower pitch)" if delta < 0 else "no shift")

    # Mach number of source
    mach   = abs(vs) / v

    steps = [
        "### Doppler Effect Report",
        f"- Source frequency ($f_s$): {fs:.4f} Hz",
        f"- Medium wave speed ($v$): {v:.4f} m/s",
        f"- Source velocity ($v_s$, +away): {vs:.4f} m/s  (Mach {mach:.4f})",
        f"- Observer velocity ($v_o$, +toward): {vo:.4f} m/s",
        "",
        f"**Observed frequency ($f_o$):** {f_obs:.4f} Hz",
        f"- Frequency shift ($\\Delta f$): {delta:+.4f} Hz  → {shift}",
        "",
        "#### Formula",
        r"$f_o = f_s \dfrac{v + v_o}{v + v_s}$",
    ]
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_kinematics(params):
    yield {"type": "step", "content": "Applying Kinematic Equations (SUVAT)..."}

    vals = {
        "u": _safe_float(params.get("u", params.get("vi",  None)), None),
        "v": _safe_float(params.get("v", params.get("vf",  None)), None),
        "a": _safe_float(params.get("a",                   None),  None),
        "t": _safe_float(params.get("t",                   None),  None),
        "s": _safe_float(params.get("s", params.get("d",   None)), None),
    }
    # Re-parse: map passed default back to None properly
    raw_params = {
        "u": params.get("u", params.get("vi")),
        "v": params.get("v", params.get("vf")),
        "a": params.get("a"),
        "t": params.get("t"),
        "s": params.get("s", params.get("d")),
    }
    vals = {k: (float(v) if v not in (None, "", "None") else None)
            for k, v in raw_params.items()}

    def known(*keys):
        return all(vals[k] is not None for k in keys)

    changed = True
    while changed:
        changed = False
        if vals["v"] is None and known("u", "a", "t"):
            vals["v"] = vals["u"] + vals["a"] * vals["t"];                    changed = True
        if vals["s"] is None and known("u", "a", "t"):
            vals["s"] = vals["u"] * vals["t"] + 0.5 * vals["a"] * vals["t"]**2; changed = True
        if vals["s"] is None and known("u", "v", "t"):
            vals["s"] = 0.5 * (vals["u"] + vals["v"]) * vals["t"];           changed = True
        if vals["a"] is None and known("u", "v", "t") and vals["t"] != 0:
            vals["a"] = (vals["v"] - vals["u"]) / vals["t"];                  changed = True
        if vals["a"] is None and known("u", "v", "s") and vals["s"] != 0:
            vals["a"] = (vals["v"]**2 - vals["u"]**2) / (2 * vals["s"]);     changed = True
        if vals["u"] is None and known("v", "a", "t"):
            vals["u"] = vals["v"] - vals["a"] * vals["t"];                    changed = True
        if vals["t"] is None and known("u", "v", "a") and vals["a"] != 0:
            vals["t"] = (vals["v"] - vals["u"]) / vals["a"];                  changed = True
        if vals["v"] is None and known("u", "a", "s"):
            disc = vals["u"]**2 + 2 * vals["a"] * vals["s"]
            if disc >= 0:
                vals["v"] = np.sqrt(disc);                                    changed = True

    steps = ["### Kinematics: 1-D Motion Analysis (SUVAT)"]

    resolved = [f"- **{k}** = {vals[k]:.6g}" for k in ("u", "v", "a", "t", "s")
                if vals[k] is not None]
    if resolved:
        steps.extend(resolved)
    else:
        steps.append("Provide at least 3 of the 5 SUVAT variables to solve for the rest.")

    steps.extend([
        "",
        "#### SUVAT Relations",
        r"- $v = u + at$",
        r"- $s = ut + \frac{1}{2}at^2$",
        r"- $v^2 = u^2 + 2as$",
        r"- $s = \frac{u+v}{2} \cdot t$",
    ])
    yield {"type": "final", "answer": "\n".join(steps)}
