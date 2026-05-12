import numpy as np

R_UNIVERSAL = 8.314


def series_points(x_values, y_values):
    return [{"x": float(x), "y": float(y)} for x, y in zip(x_values, y_values)]


async def solve_thermo(data):
    yield {"type": "step", "content": "Initializing Thermodynamics Engine..."}

    params = data.get("parameters", {})
    raw = data.get("raw_query", "").lower()
    pt = data.get("problem_type", "").lower()

    try:
        if any(keyword in pt or keyword in raw for keyword in ["ideal gas", "gas", "pv=nrt"]):
            async for chunk in solve_ideal_gas(params):
                yield chunk
        elif any(keyword in pt or keyword in raw for keyword in ["heat", "specific", "calorimetry"]):
            async for chunk in solve_heat_transfer(params):
                yield chunk
        elif any(keyword in pt or keyword in raw for keyword in ["entropy", "reversible", "isentropic"]):
            async for chunk in solve_entropy(params):
                yield chunk
        elif any(keyword in pt or keyword in raw for keyword in ["cycle", "carnot", "otto", "rankine", "refrigerator"]):
            async for chunk in solve_cycles(params):
                yield chunk
        elif any(keyword in pt or keyword in raw for keyword in ["conduction", "wall", "heat flux"]):
            async for chunk in solve_conduction(params):
                yield chunk
        elif any(keyword in pt or keyword in raw for keyword in ["polytropic", "compression", "expansion"]):
            async for chunk in solve_polytropic(params):
                yield chunk
        else:
            yield {"type": "final", "answer": "Thermodynamic problem detected, but I need a clearer type such as ideal gas, heat transfer, entropy, cycle, conduction, or polytropic process."}
    except Exception as e:
        yield {"type": "final", "answer": f"Thermo Solver Error: {str(e)}"}


async def solve_ideal_gas(params):
    yield {"type": "step", "content": "Applying the ideal gas equation of state..."}
    p = params.get("p")
    v = params.get("v", params.get("V"))
    n = params.get("n")
    t = params.get("t", params.get("T"))
    R = float(params.get("R", R_UNIVERSAL))

    p = None if p in (None, "") else float(p)
    v = None if v in (None, "") else float(v)
    n = None if n in (None, "") else float(n)
    t = None if t in (None, "") else float(t)

    if p is None and None not in (v, n, t) and v != 0:
        p = n * R * t / v
    elif v is None and None not in (p, n, t) and p != 0:
        v = n * R * t / p
    elif n is None and None not in (p, v, t) and R * t != 0:
        n = p * v / (R * t)
    elif t is None and None not in (p, v, n) and n * R != 0:
        t = p * v / (n * R)
    else:
        if any(value is None for value in (p, v, n, t)):
            yield {"type": "final", "answer": "Ideal gas calculations need any three of $P$, $V$, $n$, and $T$."}
            return

    x = np.array([1, 2, 3])
    y = np.array([p / 1000, v, t])
    yield {"type": "diagram", "diagram_type": "pv_diagram", "data": series_points(x, y)}

    steps = [
        "### Ideal Gas Law Analysis",
        f"- Pressure: {p:.3f} Pa",
        f"- Volume: {v:.6f} m^3",
        f"- Amount: {n:.6f} mol",
        f"- Temperature: {t:.3f} K",
        f"- Validation: $PV = {p * v:.3f}$ and $nRT = {n * R * t:.3f}$",
    ]
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_heat_transfer(params):
    yield {"type": "step", "content": "Calculating sensible heat transfer..."}
    m = float(params.get("m", 1))
    c = float(params.get("c", 4186))
    dt = float(params.get("dt", params.get("delta_t", 10)))
    q = m * c * dt

    yield {"type": "final", "answer": f"### Calorimetry Report\n- Mass: {m:.4f} kg\n- Specific heat: {c:.4f} J/(kg·K)\n- Temperature change: {dt:.4f} K\n- Heat transferred: {q:.4f} J"}


async def solve_entropy(params):
    yield {"type": "step", "content": "Evaluating entropy change and thermal irreversibility metrics..."}
    q = float(params.get("q", 0))
    t = float(params.get("t", params.get("T", 298.15)))
    cp = params.get("cp")
    t1 = params.get("t1")
    t2 = params.get("t2")

    ds = q / t if t else 0.0
    steps = [
        "### Entropy Analysis",
        f"- Heat interaction: {q:.4f} J",
        f"- Reference temperature: {t:.4f} K",
        f"- Entropy change from $Q/T$: {ds:.6f} J/K",
    ]

    if cp not in (None, "") and t1 not in (None, "") and t2 not in (None, ""):
        cp = float(cp)
        t1 = float(t1)
        t2 = float(t2)
        if t1 > 0 and t2 > 0:
            ds_temp = cp * np.log(t2 / t1)
            steps.append(f"- Entropy change from $c_p \\ln(T_2/T_1)$: {ds_temp:.6f} J/(kg·K)")

    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_cycles(params):
    yield {"type": "step", "content": "Computing thermal cycle efficiency limits..."}
    th = float(params.get("th", params.get("t_high", 500)))
    tl = float(params.get("tl", params.get("t_low", 300)))
    cop = tl / (th - tl) if th != tl else 0.0
    efficiency = 1 - (tl / th) if th else 0.0

    x = np.array([1, 2, 3, 4, 1])
    y = np.array([tl, th, th * 0.92, tl * 1.05, tl])
    yield {"type": "diagram", "diagram_type": "pv_diagram", "data": series_points(x, y)}

    steps = [
        "### Cycle Performance",
        f"- Hot reservoir temperature: {th:.4f} K",
        f"- Cold reservoir temperature: {tl:.4f} K",
        f"- Carnot efficiency: {efficiency:.6f}",
        f"- Carnot refrigerator COP: {cop:.6f}",
    ]
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_conduction(params):
    yield {"type": "step", "content": "Applying one-dimensional steady conduction through a wall..."}
    k = float(params.get("k", 45))
    A = float(params.get("A", params.get("area", 1)))
    L = float(params.get("L", params.get("thickness", 0.1)))
    t1 = float(params.get("t1", 400))
    t2 = float(params.get("t2", 300))

    q = k * A * (t1 - t2) / L if L else 0.0
    x = np.linspace(0, L, 50)
    temp = t1 + (t2 - t1) * (x / L) if L else np.full_like(x, t1)
    yield {"type": "diagram", "diagram_type": "temperature_curve", "data": series_points(x, temp)}

    yield {"type": "final", "answer": f"### Wall Conduction Analysis\n- Thermal conductivity: {k:.4f} W/(m·K)\n- Area: {A:.4f} m^2\n- Thickness: {L:.4f} m\n- Heat transfer rate: {q:.4f} W"}


async def solve_polytropic(params):
    yield {"type": "step", "content": "Evaluating a polytropic compression/expansion process..."}
    p1 = float(params.get("p1", 101325))
    v1 = float(params.get("v1", 1.0))
    p2 = float(params.get("p2", 202650))
    n = float(params.get("n_poly", params.get("n", 1.3)))

    v2 = v1 * (p1 / p2) ** (1 / n) if p2 else v1
    work = (p2 * v2 - p1 * v1) / (1 - n) if abs(1 - n) > 1e-9 else p1 * v1 * np.log(v2 / v1)

    v_path = np.linspace(v1, v2, 80)
    c = p1 * (v1 ** n)
    p_path = c / (v_path ** n)
    yield {"type": "diagram", "diagram_type": "pv_diagram", "data": series_points(v_path, p_path / 1000)}

    yield {"type": "final", "answer": f"### Polytropic Process Analysis\n- Initial pressure: {p1:.3f} Pa\n- Final pressure: {p2:.3f} Pa\n- Initial volume: {v1:.6f} m^3\n- Final volume: {v2:.6f} m^3\n- Polytropic index: {n:.4f}\n- Boundary work: {work:.4f} J"}
