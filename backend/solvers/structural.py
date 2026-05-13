# structural.py
import numpy as np
from solvers.constants import STEEL_YOUNGS_MODULUS
from solvers.utils import normalize_params, validate_physical_params


def series_points(x_values, y_values):
    return [{"x": float(x), "y": float(y)} for x, y in zip(x_values, y_values)]


async def solve_structural(sub: dict):
    yield {"type": "step", "content": "Initializing Multi-Physics Structural Analysis Engine..."}

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
        yield {"type": "step", "content": f"Mechanical context identified: {', '.join(used_vars)}"}

    if any(keyword in pt or keyword in raw for keyword in ["truss", "frame", "node", "element", "fem"]):
        async for chunk in solve_fem_structure(params):
            yield chunk
    elif any(keyword in pt or keyword in raw for keyword in ["axial", "stress", "strain", "bar"]):
        async for chunk in solve_axial_member(params):
            yield chunk
    elif any(keyword in pt or keyword in raw for keyword in ["buckling", "column", "euler"]):
        async for chunk in solve_column_buckling(params):
            yield chunk
    else:
        async for chunk in solve_beam_advanced(params, raw):
            yield chunk


async def solve_fem_structure(params):
    yield {"type": "step", "content": "Configuring Finite Element stiffness matrix for 2D structure..."}

    nodes = params.get("nodes", [[0, 0], [2, 0], [1, 1.5]])
    elements = params.get("elements", [
        [0, 1, 210e9, 0.01],
        [1, 2, 210e9, 0.01],
        [2, 0, 210e9, 0.01],
    ])
    loads = params.get("loads", {2: [0, -10000]})
    # constraints: {node_idx: [fix_ux, fix_uy]}  — 1 = fixed, 0 = free
    constraints = params.get("constraints", {0: [1, 1], 1: [0, 1]})

    num_nodes = len(nodes)
    K_global = np.zeros((2 * num_nodes, 2 * num_nodes))

    for el in elements:
        i, j, E, A = el
        xi, yi = nodes[i]
        xj, yj = nodes[j]
        L = np.sqrt((xj - xi) ** 2 + (yj - yi) ** 2)
        if L == 0:
            continue
        c = (xj - xi) / L
        s = (yj - yi) / L

        k_local = (E * A / L) * np.array([
            [ c*c,  c*s, -c*c, -c*s],
            [ c*s,  s*s, -c*s, -s*s],
            [-c*c, -c*s,  c*c,  c*s],
            [-c*s, -s*s,  c*s,  s*s],
        ])

        idx = [2 * i, 2 * i + 1, 2 * j, 2 * j + 1]
        for m in range(4):
            for n in range(4):
                K_global[idx[m], idx[n]] += k_local[m, n]

    # Build fixed DOF list via direct elimination
    fixed_dofs = []
    for node_idx, rest in constraints.items():
        if rest[0]:
            fixed_dofs.append(2 * node_idx)
        if rest[1]:
            fixed_dofs.append(2 * node_idx + 1)

    free_dofs = [d for d in range(2 * num_nodes) if d not in fixed_dofs]

    F = np.zeros(2 * num_nodes)
    for node_idx, force in loads.items():
        F[2 * node_idx]     += force[0]
        F[2 * node_idx + 1] += force[1]

    K_sub = K_global[np.ix_(free_dofs, free_dofs)]
    F_sub = F[free_dofs]

    try:
        U_sub = np.linalg.solve(K_sub, F_sub)
        U = np.zeros(2 * num_nodes)
        U[free_dofs] = U_sub

        F_react = K_global @ U

        yield {"type": "step", "content": "Structure resolved. Computing element stresses and nodal reactions..."}

        yield {
            "type": "diagram",
            "diagram_type": "truss_fem",
            "data": {
                "nodes": nodes,
                "elements": [(int(el[0]), int(el[1])) for el in elements],
                "U": U.tolist(),
                "scale": 1000,
            },
        }

        ans = ["### 2D Truss FEM Analysis", "#### Displacements (m)"]
        for i in range(num_nodes):
            ux, uy = U[2 * i], U[2 * i + 1]
            ans.append(f"- Node {i}: $\\delta_x = {ux:.4e}$, $\\delta_y = {uy:.4e}$")

        ans.append("#### Reactions (N)")
        for dof in fixed_dofs:
            node_idx = dof // 2
            dir_str = "X" if dof % 2 == 0 else "Y"
            ans.append(f"- Node {node_idx} {dir_str}-Reaction: {F_react[dof]:.2f} N")

        yield {"type": "final", "answer": "\n".join(ans)}

    except Exception as e:
        yield {"type": "final", "answer": f"FEM Solve Error: System might be unstable or singular. {str(e)}"}


async def solve_beam_advanced(params, raw):
    yield {"type": "step", "content": "Initializing Advanced Beam Superposition Kernel..."}

    L = float(params.get("L", params.get("l", 6)))
    if L <= 0:
        L = 6.0
    E = float(params.get("E", params.get("e", STEEL_YOUNGS_MODULUS)))
    I = float(params.get("I", params.get("i", 1e-4)))

    is_cantilever = (
        any(k in raw for k in ["cantilever", "fixed"])
        or params.get("type") == "cantilever"
    )

    point_loads = []
    udls = []

    if "simply supported" in raw and "point load" in raw and "distributed load" in raw:
        yield {"type": "step", "content": "Combined loading detected (Superposition of Point Load & UDL)."}
        p_val = params.get("P", 1000)
        w_val = params.get("w", 500)
        point_loads = [{"P": float(p_val), "a": L / 2}]
        udls = [{"w": float(w_val), "start": 0.0, "end": L}]
    else:
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

    yield {
        "type": "step",
        "content": (
            f"Resolving statics for $L = {L}$ m, "
            f"loads: {len(point_loads)} concentrated, {len(udls)} distributed..."
        ),
    }

    # Reactions via statics
    total_m_A = 0.0
    total_V = 0.0
    for p in point_loads:
        total_m_A += p["P"] * p["a"]
        total_V += p["P"]
    for w in udls:
        mag = w["w"] * (w["end"] - w["start"])
        center = (w["start"] + w["end"]) / 2
        total_m_A += mag * center
        total_V += mag

    if is_cantilever:
        RA = total_V
        MA = total_m_A
        RB = 0.0
    else:
        RB = total_m_A / L if L else 0.0
        RA = total_V - RB
        MA = 0.0

    def macaulay(x, a, n):
        val = np.maximum(0.0, x - a)
        if n == 0:
            return np.where(x >= a, 1.0, 0.0)
        return val ** n

    def v_v(x):
        res = RA * macaulay(x, 0, 0)
        for p in point_loads:
            res -= p["P"] * macaulay(x, p["a"], 0)
        for w in udls:
            res -= w["w"] * (macaulay(x, w["start"], 1) - macaulay(x, w["end"], 1))
        return res

    def v_m(x):
        res = RA * macaulay(x, 0, 1) - MA * macaulay(x, 0, 0)
        for p in point_loads:
            res -= p["P"] * macaulay(x, p["a"], 1)
        for w in udls:
            res -= 0.5 * w["w"] * (macaulay(x, w["start"], 2) - macaulay(x, w["end"], 2))
        return res

    x = np.linspace(0, L, 500)
    M = v_m(x)
    dx = L / (len(x) - 1)

    slope_raw   = np.cumsum(M) * dx
    deflect_raw = np.cumsum(slope_raw) * dx

    if is_cantilever:
        EI_slope   = slope_raw - slope_raw[0]
        EI_deflect = deflect_raw - deflect_raw[0]
    else:
        EI_deflect = deflect_raw - np.linspace(deflect_raw[0], deflect_raw[-1], len(x))
        EI_slope   = np.gradient(EI_deflect, dx)

    y     = EI_deflect / (E * I)
    theta = EI_slope   / (E * I)

    max_def = float(np.max(np.abs(y)))
    max_pos = float(x[np.argmax(np.abs(y))])
    slope_A = float(theta[0])
    slope_B = float(theta[-1])

    yield {
        "type": "diagram",
        "diagram_type": "beam_analysis",
        "data": {
            "x":               x.tolist(),
            "deflection":      y.tolist(),
            "slope":           theta.tolist(),
            "max_deflection":  max_def,
            "max_pos":         max_pos,
            "RA":              float(RA),
            "RB":              float(RB),
            "MA":              float(MA),
        },
    }

    ans = [
        "### Advanced Beam Deflection Report",
        f"- **Configuration:** {'Cantilever' if is_cantilever else 'Simply Supported'}",
        "#### Support Reactions",
        f"- $R_A = {RA:.2f}$ N",
        f"- $R_B = {RB:.2f}$ N",
    ]
    if is_cantilever:
        ans.append(f"- $M_A$ (Fixed end) $= {MA:.2f}$ N·m")
    ans += [
        "#### Kinematic Results",
        f"- **Maximum Deflection ($\\delta_{{max}}$):** ${max_def * 1000:.4f}$ mm at $x = {max_pos:.3f}$ m",
        f"- **End Slope at A ($\\theta_A$):** ${np.degrees(slope_A):.4f}^\\circ$",
        f"- **End Slope at B ($\\theta_B$):** ${np.degrees(slope_B):.4f}^\\circ$",
        f"- **Beam Stiffness ($EI$):** ${E * I:.2e}$ N·m²",
    ]
    yield {"type": "final", "answer": "\n".join(ans)}


async def solve_axial_member(params):
    yield {"type": "step", "content": "Computing axial stress, strain, and extension in a member..."}

    P = float(params.get("P", params.get("force", 0)))
    A = float(params.get("A", params.get("area", 0.01)))
    L = float(params.get("L", params.get("length", 1.0)))
    E = float(params.get("E", params.get("youngs_modulus", STEEL_YOUNGS_MODULUS)))

    stress    = P / A if A else 0.0
    strain    = stress / E if E else 0.0
    extension = strain * L

    x           = np.linspace(0, L, 60)
    deformation = (extension * (x / L)) if L else np.zeros_like(x)

    yield {
        "type": "diagram",
        "diagram_type": "displacement_curve",
        "data": series_points(x, deformation * 1000),
    }

    steps = [
        "### Axial Member Analysis",
        f"- Axial force: {P:.4f} N",
        f"- Area: {A:.6f} m²",
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

    x    = np.linspace(0, L, 120)
    mode = np.sin(np.pi * x / max(L, 1e-6))

    yield {
        "type": "diagram",
        "diagram_type": "displacement_curve",
        "data": series_points(x, mode),   # ← was truncated/corrupted in original
    }

    steps = [
        "### Column Buckling Analysis",
        f"- Young's modulus: {E:.4f} Pa",
        f"- Second moment of area: {I:.8f} m⁴",
        f"- Effective length factor: {K:.4f}",
        f"- Critical Euler load: {p_cr:.4f} N",
    ]
    yield {"type": "final", "answer": "\n".join(steps)}
