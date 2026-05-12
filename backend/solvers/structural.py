import numpy as np
from solvers.constants import STEEL_YOUNGS_MODULUS
from solvers.utils import normalize_params, validate_physical_params

def series_points(x_values, y_values):
    return [{"x": float(x), "y": float(y)} for x, y in zip(x_values, y_values)]


async def solve_structural(sub: dict):
    yield {"type": "step", "content": "Initializing Structural Analysis Engine..."}
    
    params = normalize_params(sub.get("parameters", {}))
    
    # Physical validation
    is_valid, err = validate_physical_params(params)
    if not is_valid:
        yield {"type": "error", "message": err}
        return

    raw = sub.get("raw_query", "").lower()
    pt = sub.get("problem_type", "").lower()
    
    # Display variables used
    used_vars = [k for k in params.keys() if params[k] is not None]
    if used_vars:
        yield {"type": "step", "content": f"Parameters detected: {', '.join(used_vars)}"}

    if any(keyword in pt or keyword in raw for keyword in ["axial", "stress", "strain", "bar"]):
        async for chunk in solve_axial_member(params):
            yield chunk
    elif any(keyword in pt or keyword in raw for keyword in ["buckling", "column", "euler"]):
        async for chunk in solve_column_buckling(params):
            yield chunk
    else:
        async for chunk in solve_beam_advanced(params, raw):
            yield chunk


async def solve_beam_advanced(params, raw):
    yield {"type": "step", "content": "Analyzing beam using equilibrium, shear, moment, and deflection relations..."}

    L = float(params.get("L", params.get("l", 6)))
    if L <= 0: L = 6.0
    E = float(params.get("E", params.get("e", STEEL_YOUNGS_MODULUS)))
    I = float(params.get("I", params.get("i", 1e-4)))
    point_loads = params.get("point_loads", [])
    if not point_loads:
        p_val = params.get("P", params.get("F", params.get("force")))
        if p_val is not None:
            point_loads = [{"P": float(p_val), "a": float(params.get("a", params.get("pos", L / 2)))}]

    udls = params.get("udls", [])
    if not udls:
        w_val = params.get("w", params.get("udl"))
        if w_val is not None:
            udls = [{"w": float(w_val), "start": 0.0, "end": L}]

    total_moment_about_a = 0.0
    total_vertical_load = 0.0
    for load in point_loads:
        total_moment_about_a += load["P"] * load["a"]
        total_vertical_load += load["P"]
    for load in udls:
        load_mag = load["w"] * (load["end"] - load["start"])
        centroid = (load["start"] + load["end"]) / 2
        total_moment_about_a += load_mag * centroid
        total_vertical_load += load_mag

    is_cantilever = "cantilever" in raw or params.get("type") == "cantilever"
    if is_cantilever:
        RA = total_vertical_load
        RB = 0.0
        MA = total_moment_about_a
    else:
        RB = total_moment_about_a / L if L else 0.0
        RA = total_vertical_load - RB
        MA = 0.0

    def macaulay(x, a, n):
        return np.where(x >= a, (x - a) ** n, 0.0)

    def get_shear(x):
        value = RA * macaulay(x, 0, 0)
        for load in point_loads:
            value -= load["P"] * macaulay(x, load["a"], 0)
        for load in udls:
            value -= load["w"] * (macaulay(x, load["start"], 1) - macaulay(x, load["end"], 1))
        return value

    def get_moment(x):
        value = RA * macaulay(x, 0, 1) - MA * macaulay(x, 0, 0)
        for load in point_loads:
            value -= load["P"] * macaulay(x, load["a"], 1)
        for load in udls:
            value -= 0.5 * load["w"] * (macaulay(x, load["start"], 2) - macaulay(x, load["end"], 2))
        return value

    x = np.linspace(0, L, 300)
    shear = get_shear(x)
    moment = get_moment(x)
    slope = np.cumsum(moment) * (L / max(len(x) - 1, 1)) / (E * I)
    if is_cantilever:
        slope -= slope[0]
    deflection = np.cumsum(slope) * (L / max(len(x) - 1, 1))
    if not is_cantilever and len(deflection) > 1:
        deflection -= np.linspace(deflection[0], deflection[-1], len(deflection))

    critical_points = sorted(list(set([0, L, L / 2] + [load["a"] for load in point_loads])))
    table_rows = []
    for point in critical_points:
        table_rows.append({
            "Position (m)": round(float(point), 4),
            "Shear (N)": round(float(get_shear(np.array([point]))[0]), 4),
            "Moment (Nm)": round(float(get_moment(np.array([point]))[0]), 4),
        })

    yield {
        "type": "table",
        "title": "Beam section results",
        "columns": ["Position (m)", "Shear (N)", "Moment (Nm)"],
        "rows": table_rows,
    }
    yield {
        "type": "diagram",
        "diagram_type": "beam_analysis",
        "data": {
            "x": x.tolist(),
            "shear": shear.tolist(),
            "moment": moment.tolist(),
            "length": L,
            "max_shear": float(np.max(np.abs(shear))),
            "max_moment": float(np.max(np.abs(moment))),
            "max_deflection": float(np.max(np.abs(deflection))),
            "type": "cantilever" if is_cantilever else "simply_supported",
        },
    }

    answer = [
        "### Beam Analysis Report",
        f"- Configuration: {'Cantilever' if is_cantilever else 'Simply supported'}",
        f"- Left reaction: {RA:.4f} N",
        f"- Right reaction: {RB:.4f} N",
        f"- Fixed-end moment: {MA:.4f} N·m",
        f"- Maximum shear: {np.max(np.abs(shear)):.4f} N",
        f"- Maximum moment: {np.max(np.abs(moment)):.4f} N·m",
        f"- Maximum deflection: {np.max(np.abs(deflection)) * 1000:.6f} mm",
    ]
    yield {"type": "final", "answer": "\n".join(answer)}


async def solve_axial_member(params):
    yield {"type": "step", "content": "Computing axial stress, strain, and extension in a member..."}
    P = float(params.get("P", params.get("force", 0)))
    A = float(params.get("A", params.get("area", 0.01)))
    L = float(params.get("L", params.get("length", 1.0)))
    E = float(params.get("E", params.get("youngs_modulus", STEEL_YOUNGS_MODULUS)))

    stress = P / A if A else 0.0
    strain = stress / E if E else 0.0
    extension = strain * L

    x = np.linspace(0, L, 60)
    deformation = extension * (x / L) if L else np.zeros_like(x)
    yield {"type": "diagram", "diagram_type": "displacement_curve", "data": series_points(x, deformation * 1000)}

    steps = [
        "### Axial Member Analysis",
        f"- Axial force: {P:.4f} N",
        f"- Area: {A:.6f} m^2",
        f"- Stress: {stress:.4f} Pa",
        f"- Strain: {strain:.8f}",
        f"- Extension: {extension:.8f} m",
    ]
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_column_buckling(params):
    yield {"type": "step", "content": "Applying Euler column buckling theory..."}
    E = float(params.get("E", params.get("youngs_modulus", STEEL_YOUNGS_MODULUS)))
    I = float(params.get("I", params.get("i", 1e-6)))
    L = float(params.get("L", params.get("length", 2.0)))
    K = float(params.get("K", params.get("effective_length_factor", 1.0)))

    p_cr = (np.pi ** 2 * E * I) / ((K * L) ** 2) if K * L else 0.0
    x = np.linspace(0, L, 120)
    mode = np.sin(np.pi * x / max(L, 1e-6))
    yield {"type": "diagram", "diagram_type": "displacement_curve", "data": series_points(x, mode)}

    steps = [
        "### Column Buckling Analysis",
        f"- Young's modulus: {E:.4f} Pa",
        f"- Second moment of area: {I:.8f} m^4",
        f"- Effective length factor: {K:.4f}",
        f"- Critical Euler load: {p_cr:.4f} N",
    ]
    yield {"type": "final", "answer": "\n".join(steps)}
