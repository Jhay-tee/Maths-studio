import asyncio
import numpy as np
import cmath

from solvers.utils import normalize_params, validate_physical_params

async def solve_circuits(data):
    yield {"type": "step", "content": "Initializing Circuit Analysis Kernel..."}
    
    params = normalize_params(data.get("parameters", {}))
    
    # Physical validation
    is_valid, err = validate_physical_params(params)
    if not is_valid:
        yield {"type": "error", "message": err}
        return
        
    raw = data.get("raw_query", "").lower()
    
    # Display variables used
    used_vars = [k for k in params.keys() if params[k] is not None]
    if used_vars:
        yield {"type": "step", "content": f"Components detected: {', '.join(used_vars)}"}
    
    try:
        if "ac" in raw or "impedance" in raw or "phasor" in raw:
            async for chunk in solve_ac_impedance(params):
                yield chunk
        elif "ohm" in raw or "resistance" in raw or "v=ir" in raw:
            async for chunk in solve_ohms_law(params):
                yield chunk
        elif "series" in raw or "parallel" in raw:
            async for chunk in solve_resistor_network(params):
                yield chunk
        elif "capacitor" in raw or "rc" in raw:
            async for chunk in solve_rc_circuit(params):
                yield chunk
        else:
            yield {"type": "step", "content": "Applying KVL/KCL..."}
            yield {"type": "final", "answer": "Circuit analysis complete. No specific component values detected for full nodal simulation."}
    except Exception as e:
        yield {"type": "final", "answer": f"Circuit Solver Error: {str(e)}"}

async def solve_ohms_law(params):
    v = float(params.get("v", params.get("voltage", 0)))
    i = float(params.get("i", params.get("current", 0)))
    r = float(params.get("r", params.get("resistance", 0)))

    steps = ["### Ohm's Law Resolution"]
    result_v, result_i, result_r = v, i, r

    if v and i:
        result_r = v / i
        steps.append(f"- Calculated Resistance: $R = V/I = {result_r:.2f}$ $\\Omega$")
    elif v and r:
        result_i = v / r
        steps.append(f"- Calculated Current: $I = V/R = {result_i:.4f}$ A")
    elif i and r:
        result_v = i * r
        steps.append(f"- Calculated Voltage: $V = I \\cdot R = {result_v:.2f}$ V")
    else:
        steps.append("Please provide at least two parameters out of V, I, R.")

    # Emit circuit diagram
    diagram_data = {
        "voltage": result_v,
        "current": result_i,
        "resistance": result_r,
        "power": result_v * result_i if result_v and result_i else 0
    }
    yield {"type": "diagram", "diagram_type": "circuit_ohms", "data": diagram_data}
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_resistor_network(params):
    yield {"type": "step", "content": "Analyzing Resistor Network..."}
    resistors = params.get("resistors", [])
    mode = params.get("mode", "series") # "series" or "parallel"

    if not resistors:
        yield {"type": "final", "answer": "No resistor values found. Please provide a list of resistances."}
        return

    if mode == "series":
        req = sum(resistors)
    else:
        req = 1 / sum(1/r for r in resistors)

    steps = [
        f"### {mode.capitalize()} Resistor Analysis",
        f"- Components: {resistors} $\\Omega$",
        f"- **Equivalent Resistance ($R_{{eq}}$):** {req:.2f} $\\Omega$"
    ]

    diagram_data = {
        "resistors": resistors,
        "mode": mode,
        "equivalent": req
    }
    yield {"type": "diagram", "diagram_type": "resistor_network", "data": diagram_data}
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_rc_circuit(params):
    yield {"type": "step", "content": "Analyzing Transient RC Response..."}
    r = float(params.get("r", 1000)) # 1k
    c = float(params.get("c", 1e-6)) # 1uF
    
    tau = r * c
    steps = [
        "### RC Time Constant Analysis",
        f"- Resistance ($R$): {r} $\\Omega$",
        f"- Capacitance ($C$): {c*1e6:.1f} $\\mu$F",
        f"**Time Constant ($\\tau$):** $RC = {tau*1000:.3f}$ ms",
        f"- Settling Time (99%): $5\\tau = {5*tau*1000:.3f}$ ms"
    ]
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_ac_impedance(params):
    yield {"type": "step", "content": "Calculating Complex AC Impedance..."}
    f = float(params.get("f", 60)) # Hz
    w = 2 * np.pi * f
    
    r = float(params.get("r", 0))
    l = float(params.get("l", 0))
    c = float(params.get("c", 0))
    
    # Impedances
    z_r = complex(r, 0)
    z_l = complex(0, w * l) if l > 0 else 0
    z_c = complex(0, -1 / (w * c)) if c > 0 else 0
    
    z_total = z_r + z_l + z_c
    mag = abs(z_total)
    phase = np.degrees(cmath.phase(z_total))
    
    steps = [
        "### AC Impedance Analysis (RLC Series)",
        f"- Frequency ($f$): {f} Hz ($\\omega = {w:.2f}$ rad/s)",
        f"- Resistance ($R$): {r} $\\Omega$",
        f"- Inductance ($L$): {l*1000:.1f} mH $\\rightarrow Z_L = {z_l.imag:.2f}j$",
        f"- Capacitance ($C$): {c*1e6:.1f} $\\mu$F $\\rightarrow Z_C = {z_c.imag:.2f}j$",
        "#### Resulting Impedance",
        f"- **Rectangular:** $Z = {z_total.real:.2f} + {z_total.imag:.2f}j$ $\\Omega$",
        f"- **Polar:** $|Z| = {mag:.2f} \\Omega$, $\\angle{phase:.2f}^\\circ$"
    ]
    yield {"type": "final", "answer": "\n".join(steps)}
