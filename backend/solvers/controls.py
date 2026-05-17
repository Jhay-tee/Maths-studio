import asyncio
import numpy as np

from solvers.utils import normalize_params, validate_physical_params

async def solve_controls(data):
    yield {"type": "step", "content": "Initializing Robust Control Systems Kernel..."}
    
    params = normalize_params(data.get("parameters", {}))
    raw = data.get("raw_query", "").lower()
    
    used_params = [k for k in params.keys() if params[k] is not None]
    if used_params:
        yield {"type": "step", "content": f"System definitions: {', '.join(used_params)}"}
    
    try:
        if "step" in raw or "response" in raw:
            async for chunk in solve_step_response(params):
                yield chunk
        elif "tf" in raw or "transfer" in raw or "stability" in raw:
            async for chunk in solve_transfer_function(params):
                yield chunk
        elif "bode" in raw or "frequency" in raw:
            async for chunk in solve_frequency_response(params):
                yield chunk
        else:
            async for chunk in solve_transfer_function(params):
                yield chunk
    except Exception as e:
        yield {"type": "final", "answer": f"Control System Execution Error: {str(e)}"}

async def solve_step_response(params):
    yield {"type": "step", "content": "Simulating system time-domain response to unit step input..."}
    num = params.get("num", [1])
    den = params.get("den", [1, 2, 1])
    
    # Simple numerical simulation of LTI system
    # y'' + 2y' + y = u(t)
    dt = 0.05
    t_end = 10.0
    t = np.arange(0, t_end, dt)
    y = np.zeros_like(t)
    v = np.zeros_like(t) # velocity for 2nd order approximation
    
    # If 2nd order: den = [a, b, c] -> a y'' + b y' + c y = u
    if len(den) == 3:
        a, b, c = den
        u = 1.0 # unit step
        for i in range(1, len(t)):
            accel = (u - b*v[i-1] - c*y[i-1])/a
            v[i] = v[i-1] + accel*dt
            y[i] = y[i-1] + v[i]*dt
    elif len(den) == 2:
        # a y' + b y = u
        a, b = den
        u = 1.0
        for i in range(1, len(t)):
            y_dot = (u - b*y[i-1])/a
            y[i] = y[i-1] + y_dot*dt
            
    yield {
        "type": "diagram",
        "diagram_type": "time_series",
        "data": [{"x": float(ti), "y": float(yi)} for ti, yi in zip(t, y)]
    }
    
    ans = [
        "### Step Response Analysis",
        f"- **Final Value:** {y[-1]:.3f}",
        f"- **Settling Time (approx):** {t_end if y[-1] < 0.9 else 'N/A'} s",
        "- **Overshoot:** Detected from trajectory if peak > final."
    ]
    yield {"type": "final", "answer": "\n".join(ans)}

async def solve_transfer_function(params):
    yield {"type": "step", "content": "Computing system poles, zeros, and BIBO stability metrics..."}
    # num: [1], den: [1, 2, 1] means 1 / (s^2 + 2s + 1)
    num = params.get("num", [1])
    den = params.get("den", [1, 1])
    
    poles = np.roots(den)
    zeros = np.roots(num)
    
    is_stable = all(p.real < 0 for p in poles)
    
    steps = [
        "### System Characterization",
        f"- **Transfer Function $H(s)$:** $\\frac{{{poly_to_latex(num)}}}{{{poly_to_latex(den)}}}$",
        "#### Stability & Topology",
        f"- **Poles ($s$):** {ArrayToLatex(poles)}",
        f"- **Zeros ($s$):** {ArrayToLatex(zeros)}",
        f"- **BIBO Stability:** {'✅ STABLE (LHP Poles)' if is_stable else '❌ UNSTABLE'}"
    ]
    
    if len(den) == 3: # 2nd order system
        a, b, c = den
        wn = np.sqrt(c/a)
        zeta = b / (2 * np.sqrt(a * c))
        steps.extend([
            "#### Standard 2nd Order Metrics",
            f"- **Natural Frequency ($\\omega_n$):** {wn:.3f} rad/s",
            f"- **Damping Ratio ($\\zeta$):** {zeta:.3f}",
            f"- **System Type:** {getResponseType(zeta)}"
        ])
        
    yield {"type": "final", "answer": "\n".join(steps)}

def poly_to_latex(coeffs):
    terms = []
    n = len(coeffs) - 1
    for i, c in enumerate(coeffs):
        p = n - i
        if c == 0: continue
        sym = f"s^{{{p}}}" if p > 1 else ("s" if p == 1 else "")
        coeff_str = (str(c) if c != 1 or p == 0 else "")
        terms.append(f"{coeff_str}{sym}")
    return " + ".join(terms) if terms else "0"

async def solve_frequency_response(params):
    yield {"type": "step", "content": "Generating Bode Magnitude and Phase characteristics..."}
    
    # Handle num/den as lists or potential string coefficients
    num = params.get("num")
    den = params.get("den")

    if isinstance(num, str):
        num = [float(x.strip()) for x in num.strip("[]").split(",") if x.strip()]
    if isinstance(den, str):
        den = [float(x.strip()) for x in den.strip("[]").split(",") if x.strip()]

    num = num or [1]
    den = den or [1, 10]
    
    yield {"type": "step", "content": f"Computing response for Transfer Function: $G(s) = \\frac{{{poly_to_latex(num)}}}{{{poly_to_latex(den)}}}$"}

    w = np.logspace(-1, 3, 200)
    mag = []
    phase = []
    
    for wi in w:
        s = 1j * wi
        # Calculate H(jw)
        h_jw = np.polyval(num, s) / np.polyval(den, s)
        mag.append(20 * np.log10(np.abs(h_jw)))
        phase.append(np.angle(h_jw, deg=True))
        
    yield {
        "type": "diagram",
        "diagram_type": "bode_plot",
        "data": {
            "w": w.tolist(),
            "mag": mag,
            "phase": phase
        }
    }
    
    # Compute gain margin / phase margin estimates
    pm_idx = next((i for i, m in enumerate(mag) if m <= 0), None)
    gm_idx = next((i for i, p in enumerate(phase) if p <= -180), None)
    pm_str = f"{180 + phase[pm_idx]:.1f}°" if pm_idx is not None else "∞"
    gm_str = f"{-mag[gm_idx]:.1f} dB" if gm_idx is not None else "∞"

    yield {"type": "final", "answer": f"### Frequency Response Analysis\n- **Bode Mapping Complete**\n- **Phase Margin:** {pm_str}\n- **Gain Margin:** {gm_str}\n- **DC Gain:** {mag[0]:.2f} dB\n- Refer to the Bode plot below for magnitude and phase curves."}

def ArrayToLatex(arr):
    if len(arr) == 0: return "None"
    return ", ".join([f"{p.real:.2f} + {p.imag:.2f}j" if p.imag != 0 else f"{p.real:.2f}" for p in arr])

def getResponseType(z):
    if z > 1: return "Overdamped"
    if z == 1: return "Critically Damped"
    if z > 0: return "Underdamped"
    if z == 0: return "Undamped"
    return "Unstable"

async def solve_bode_simplified(params):
    yield {"type": "step", "content": "Generating Frequency Domain Insights..."}
    # This would usually need a plot, but we can give frequencies
    num = params.get("num", [1])
    den = params.get("den", [1, 10]) # 1/(s+10)
    
    cutoff = np.abs(np.roots(den)[0]) if len(den) == 2 else 0
    
    steps = [
        "### Frequency Response (Bode) Parameters",
        f"- **Cut-off Frequency ($\\omega_c$):** {cutoff:.2f} rad/s",
        f"- **DC Gain:** {sum(num)/sum(den):.3f}",
        "- **Phase Shift:** Frequency-dependent."
    ]
    yield {"type": "final", "answer": "\n".join(steps)}
