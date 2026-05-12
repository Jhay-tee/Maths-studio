import asyncio
import numpy as np

from solvers.utils import normalize_params, validate_physical_params

async def solve_controls(data):
    yield {"type": "step", "content": "Initializing Control Systems Kernel..."}
    
    params = normalize_params(data.get("parameters", {}))
    # Note: validation might be different for controls (roots can be anything)
    
    raw = data.get("raw_query", "").lower()
    
    # Display variables used
    used_params = [k for k in params.keys() if params[k] is not None]
    if used_params:
        yield {"type": "step", "content": f"System parameters identified: {', '.join(used_params)}"}
    
    try:
        if "transfer" in raw or "tf" in raw:
            async for chunk in solve_transfer_function(params):
                yield chunk
        elif "bode" in raw:
            async for chunk in solve_bode_simplified(params):
                yield chunk
        else:
            yield {"type": "step", "content": "Analyzing system feedback loop..."}
            yield {"type": "final", "answer": "Control analysis complete. Provide Numerator/Denominator coefficients for full Transfer Function analysis."}
    except Exception as e:
        yield {"type": "final", "answer": f"Controls Solver Error: {str(e)}"}

async def solve_transfer_function(params):
    yield {"type": "step", "content": "Calculating Transfer Function Characteristics..."}
    # num: [1], den: [1, 2, 1] means 1 / (s^2 + 2s + 1)
    num = params.get("num", [1])
    den = params.get("den", [1, 1])
    
    # Calculate poles
    poles = np.roots(den)
    zeros = np.roots(num)
    
    is_stable = all(p.real < 0 for p in poles)
    
    steps = [
        "### Transfer Function Analysis",
        f"- **Numerator Coeffs:** {num}",
        f"- **Denominator Coeffs:** {den}",
        "#### Stability & Topology",
        f"- **Poles:** {ArrayToLatex(poles)}",
        f"- **Zeros:** {ArrayToLatex(zeros)}",
        f"- **BIBO Stability:** {'✅ STABLE' if is_stable else '❌ UNSTABLE'}"
    ]
    
    if len(den) == 3: # 2nd order system
        # a s^2 + b s + c
        a, b, c = den
        wn = np.sqrt(c/a)
        zeta = b / (2 * np.sqrt(a * c))
        steps.extend([
            "#### 2nd Order Characteristics",
            f"- **Natural Frequency ($\\omega_n$):** {wn:.3f} rad/s",
            f"- **Damping Ratio ($\\zeta$):** {zeta:.3f}",
            f"- **Response Type:** {getResponseType(zeta)}"
        ])
        
    yield {"type": "final", "answer": "\n".join(steps)}

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
