"""
Structural Analysis Solver
Handles: FEM truss, beam deflection/superposition,
         axial members, column buckling.
"""

import numpy as np
from solvers.constants import STEEL_YOUNGS_MODULUS
from solvers.utils import normalize_params, validate_physical_params


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

async def solve_structural(sub: dict):
    yield {"type": "step", "content": "Initializing Multi-Physics Structural Analysis Engine..."}

    params = normalize_params(sub.get("parameters", {}))

    is_valid, err = validate_physical_params(params)
    if not is_valid:
        yield {"type": "error", "message": err}
        return

    raw = sub.get("raw_query", "").lower()
    pt  = sub.get("problem_type", "").lower()

    used_vars = [k for k, v in params.items() if v is not None]
    if used_vars:
        yield {"type": "step", "content": f"Structural parameters identified: {', '.join(used_vars)}"}

    if any(kw in pt or kw in raw for kw in ("truss", "frame", "node", "element", "fem")):
        async for chunk in solve_fem_structure(params):
            yield chunk
    elif any(kw in pt or kw in raw for kw in ("axial", "stress", "strain", "bar")):
        async for chunk in solve_axial_member(params):
            yield chunk
    elif any(kw in pt or kw in raw for kw in ("buckling", "column", "euler")):
        async for chunk in solve_column_buckling(params):
            yield chunk
    else:
        async for chunk in solve_beam_advanced(params, raw):
            yield chunk


# ---------------------------------------------------------------------------
# Sub-solvers
# ---------------------------------------------------------------------------

async def solve_fem_structure(params):
    yield {"type": "step", "content": "Assembling global stiffness matrix $[K]$..."}

    nodes       = params.get("nodes",    [[0, 0], [2, 0], [1, 1.5]])
    elements    = params.get("elements", [
        [0, 1, 210e9, 0.01],
        [1, 2, 210e9, 0.01],
        [2, 0, 210e9, 0.01],
    ])
    loads       = params.get("loads",       {2: [0, -10000]})
    constraints = params.get("constraints", {0: [1, 1], 1: [0, 1]})

    num_nodes = len(nodes)
    K_global  = np.zeros((2 * num_nodes, 2 * num_nodes))

    yield {"type": "step",
           "content": f"Structure: {num_nodes} nodes, {len(elements)} bar elements"}

    for idx_e, el in enumerate(elements):
        i, j, E, A = el
        xi, yi = nodes[int(i)]
        xj, yj = nodes[int(j)]
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
        dofs = [2*int(i), 2*int(i)+1, 2*int(j), 2*int(j)+1]
        for m in range(4):
            for n in range(4):
                K_global[dofs[m], dofs[n]] += k_local[m, n]
        yield {"type": "step",
               "content": f"Element {idx_e} (nodes {int(i)}–{int(j)}): $L={L:.4f}$ m,  $EA/L={E*A/L:.2e}$ N/m assembled"}

    fixed_dofs = []
    for node_idx, rest in constraints.items():
        if rest[0]: fixed_dofs.append(2 * int(node_idx))
        if rest[1]: fixed_dofs.append(2 * int(node_idx) + 1)

    free_dofs = [d for d in range(2 * num_nodes) if d not in fixed_dofs]

    F = np.zeros(2 * num_nodes)
    for node_idx, force in loads.items():
        F[2 * int(node_idx)]     += force[0]
        F[2 * int(node_idx) + 1] += force[1]

    yield {"type": "step",
           "content": f"DOF partition: {len(free_dofs)} free, {len(fixed_dofs)} fixed.  Solving $[K_{{ff}}]\\{{U_f\\}} = \\{{F_f\\}}$..."}

    K_sub = K_global[np.ix_(free_dofs, free_dofs)]
    F_sub = F[free_dofs]

    try:
        U_sub          = np.linalg.solve(K_sub, F_sub)
        U              = np.zeros(2 * num_nodes)
        U[free_dofs]   = U_sub
        F_react        = K_global @ U

        yield {"type": "step", "content": "System solved. Computing element stresses and reactions..."}

        # Free body diagram of whole structure
        fbd_forces = []
        for node_idx, force in loads.items():
            fbd_forces.append({
                "label": f"F@N{node_idx}=({force[0]:.0f},{force[1]:.0f}) N",
                "node": int(node_idx), "dx": 0 if force[0] == 0 else np.sign(force[0]),
                "dy": 0 if force[1] == 0 else np.sign(force[1]), "color": "#e74c3c",
            })
        for dof in fixed_dofs:
            n_idx   = dof // 2
            dir_str = "X" if dof % 2 == 0 else "Y"
            fbd_forces.append({
                "label": f"R{dir_str}@N{n_idx}={F_react[dof]:.1f} N",
                "node": n_idx, "color": "#2ecc71",
            })

        yield {
            "type": "diagram",
            "diagram_type": "free_body_diagram",
            "data": {
                "label": "2D Truss FBD",
                "nodes": nodes,
                "elements": [(int(el[0]), int(el[1])) for el in elements],
                "forces": fbd_forces,
            },
        }

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

        ans = ["### 2D Truss FEM Analysis", "#### Nodal Displacements (m)"]
        for i in range(num_nodes):
            ux, uy = U[2 * i], U[2 * i + 1]
            ans.append(f"- Node {i}: $\\delta_x = {ux:.4e}$,  $\\delta_y = {uy:.4e}$")

        ans.append("#### Support Reactions (N)")
        for dof in fixed_dofs:
            n_idx   = dof // 2
            dir_str = "X" if dof % 2 == 0 else "Y"
            ans.append(f"- Node {n_idx} {dir_str}: {F_react[dof]:.2f} N")

        yield {"type": "final", "answer": "\n".join(ans)}

    except Exception as e:
        yield {"type": "final",
               "answer": f"FEM Solve Error: system may be unstable or singular. {str(e)}"}


async def solve_beam_advanced(params, raw):
    yield {"type": "step", "content": "Setting up beam superposition analysis..."}

    L = _safe_float(params.get("L", params.get("l", 6)), 6.0)
    if L <= 0:
        L = 6.0
    E = _safe_float(params.get("E", params.get("e", STEEL_YOUNGS_MODULUS)), STEEL_YOUNGS_MODULUS)
    I = _safe_float(params.get("I", params.get("i", 1e-4)), 1e-4)

    is_cantilever = (
        any(k in raw for k in ("cantilever", "fixed"))
        or params.get("type") == "cantilever"
    )

    yield {"type": "step",
           "content": f"Configuration: {'Cantilever' if is_cantilever else 'Simply Supported'},  $L = {L}$ m,  $EI = {E*I:.3e}$ N·m²"}

    # Collect loads
    if "simply supported" in raw and "point load" in raw and "distributed load" in raw:
        yield {"type": "step", "content": "Combined loading detected — applying superposition."}
        p_val = params.get("P", 1000)
        w_val = params.get("w", 500)
        point_loads = [{"P": float(p_val), "a": L / 2}]
        udls        = [{"w": float(w_val), "start": 0.0, "end": L}]
    else:
        point_loads = list(params.get("point_loads", []))
        if not point_loads:
            p_val = params.get("P", params.get("F", params.get("force")))
            if p_val is not None:
                point_loads = [{"P": float(p_val),
                                "a": float(params.get("a", params.get("pos", L / 2)))}]
        udls = list(params.get("udls", []))
        if not udls:
            w_val = params.get("w", params.get("udl"))
            if w_val is not None:
                udls = [{"w": float(w_val), "start": 0.0, "end": L}]

    # Statics
    total_m_A = 0.0
    total_V   = 0.0
    for p in point_loads:
        total_m_A += p["P"] * p["a"]
        total_V   += p["P"]
    for w in udls:
        mag        = w["w"] * (w["end"] - w["start"])
        center     = (w["start"] + w["end"]) / 2
        total_m_A += mag * center
        total_V   += mag

    if is_cantilever:
        RA = total_V
        MA = total_m_A
        RB = 0.0
    else:
        RB = total_m_A / L if L else 0.0
        RA = total_V - RB
        MA = 0.0

    yield {"type": "step",
           "content": f"$\\sum M_A = 0 \\Rightarrow R_B \\cdot {L} = {total_m_A:.4f}$  →  $R_B = {RB:.4f}$ N"}
    yield {"type": "step",
           "content": f"$\\sum F_y = 0 \\Rightarrow R_A = {total_V:.4f} - {RB:.4f} = {RA:.4f}$ N"}

    # Free body diagram
    fbd_forces = [
        {"label": f"RA={RA:.2f} N", "x": 0, "dy":  1, "color": "#2ecc71"},
    ]
    if not is_cantilever:
        fbd_forces.append({"label": f"RB={RB:.2f} N", "x": L, "dy": 1, "color": "#2ecc71"})
    for pl in point_loads:
        fbd_forces.append({"label": f"P={pl['P']:.2f} N", "x": pl["a"], "dy": -1, "color": "#e74c3c"})

    yield {
        "type": "diagram",
        "diagram_type": "free_body_diagram",
        "data": {
            "label": f"{'Cantilever' if is_cantilever else 'Simply Supported'} Beam  (L={L} m)",
            "length": L,
            "forces": fbd_forces,
            "udls": udls,
            "MA": MA if is_cantilever else 0,
        },
    }

    # Macaulay functions
    def macaulay(x, a, n):
        val = np.maximum(0.0, x - a)
        return np.where(x >= a, 1.0, 0.0) if n == 0 else val ** n

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

    x   = np.linspace(0, L, 500)
    V_  = v_v(x)
    M_  = v_m(x)
    dx  = L / (len(x) - 1)

    yield {"type": "step",
           "content": f"Max shear = {float(np.max(np.abs(V_))):.4f} N,  max moment = {float(np.max(np.abs(M_))):.4f} N·m"}

    slope_raw   = np.cumsum(M_) * dx
    deflect_raw = np.cumsum(slope_raw) * dx

    if is_cantilever:
        EI_slope   = slope_raw   - slope_raw[0]
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

    yield {"type": "step",
           "content": f"$\\delta_{{max}} = {max_def * 1000:.4f}$ mm at $x = {max_pos:.3f}$ m"}

    yield {
        "type": "diagram",
        "diagram_type": "beam_analysis",
        "data": {
            "x": x.tolist(),
            "shear": V_.tolist(),
            "moment": M_.tolist(),
            "deflection": y.tolist(),
            "slope": theta.tolist(),
            "max_deflection": max_def,
            "max_pos": max_pos,
            "RA": float(RA),
            "RB": float(RB),
            "MA": float(MA),
        },
    }

    ans = [
        "### Advanced Beam Analysis",
        f"- Configuration: **{'Cantilever' if is_cantilever else 'Simply Supported'}**",
        f"- Span ($L$): {L} m  |  $EI = {E*I:.3e}$ N·m²",
        "",
        "#### Support Reactions",
        f"- $R_A = {RA:.4f}$ N",
        f"- $R_B = {RB:.4f}$ N",
    ]
    if is_cantilever:
        ans.append(f"- $M_A$ (fixed-end moment) $= {MA:.4f}$ N·m")
    ans += [
        "",
        "#### Kinematic Results",
        f"- Max deflection ($\\delta_{{max}}$): **{max_def * 1000:.4f} mm** at $x = {max_pos:.3f}$ m",
        f"- Slope at A ($\\theta_A$): {np.degrees(slope_A):.4f}°",
        f"- Slope at B ($\\theta_B$): {np.degrees(slope_B):.4f}°",
    ]
    yield {"type": "final", "answer": "\n".join(ans)}


async def solve_axial_member(params):
    yield {"type": "step", "content": "Computing axial stress, strain, and deformation..."}

    P = _safe_float(params.get("P", params.get("force",         0)))
    A = _safe_float(params.get("A", params.get("area",       0.01)), 0.01)
    L = _safe_float(params.get("L", params.get("length",      1.0)),  1.0)
    E = _safe_float(params.get("E", params.get("youngs_modulus", STEEL_YOUNGS_MODULUS)),
                    STEEL_YOUNGS_MODULUS)

    # Free body diagram
    yield {
        "type": "diagram",
        "diagram_type": "free_body_diagram",
        "data": {
            "label": f"Axial Bar  (L={L} m, A={A} m²)",
            "length": L,
            "forces": [
                {"label": f"P={P:.2f} N",  "x": L, "dx":  1, "dy": 0, "color": "#9b59b6"},
                {"label": f"-P={P:.2f} N", "x": 0, "dx": -1, "dy": 0, "color": "#e74c3c"},
            ],
        },
    }

    stress    = P / A  if A else 0.0
    strain    = stress / E if E else 0.0
    extension = strain * L

    yield {"type": "step", "content": f"$\\sigma = P/A = {P}/{A} = {stress:.4f}$ Pa"}
    yield {"type": "step", "content": f"$\\varepsilon = \\sigma/E = {stress:.4f}/{E:.4e} = {strain:.8f}$"}
    yield {"type": "step", "content": f"$\\delta = \\varepsilon L = {strain:.8f} \\times {L} = {extension:.8f}$ m"}

    x           = np.linspace(0, L, 60)
    deformation = (extension * (x / L)) if L else np.zeros_like(x)
    yield {"type": "diagram", "diagram_type": "displacement_curve",
           "data": series_points(x, deformation * 1000)}   # mm

    yield {
        "type": "final",
        "answer": "\n".join([
            "### Axial Member Analysis ($\\sigma = P/A$,  $\\delta = PL/AE$)",
            f"- Axial force ($P$): {P:.4f} N",
            f"- Cross-section area ($A$): {A:.6f} m²",
            f"- Young's modulus ($E$): {E:.4e} Pa",
            f"- Axial stress ($\\sigma$): **{stress:.4f} Pa**",
            f"- Axial strain ($\\varepsilon$): **{strain:.8f}**",
            f"- Elongation ($\\delta$): **{extension * 1000:.6f} mm**",
        ]),
    }


async def solve_column_buckling(params):
    yield {"type": "step", "content": "Applying Euler column buckling theory..."}

    E = _safe_float(params.get("E", params.get("youngs_modulus", STEEL_YOUNGS_MODULUS)),
                    STEEL_YOUNGS_MODULUS)
    I = _safe_float(params.get("I", params.get("i",              1e-6)), 1e-6)
    L = _safe_float(params.get("L", params.get("length",          2.0)),  2.0)
    K = _safe_float(params.get("K", params.get("effective_length_factor", 1.0)), 1.0)

    Le = K * L
    yield {"type": "step", "content": f"Effective length: $L_e = KL = {K} \\times {L} = {Le}$ m"}
    yield {"type": "step",
           "content": f"Euler load formula: $P_{{cr}} = \\pi^2 EI / L_e^2$"}
    yield {"type": "step",
           "content": f"$P_{{cr}} = \\pi^2 \\times {E:.3e} \\times {I:.3e} / {Le}^2$"}

    p_cr = (np.pi ** 2 * E * I) / (Le ** 2) if Le else 0.0
    yield {"type": "step", "content": f"$P_{{cr}} = {p_cr:.4f}$ N"}

    # Free body diagram
    yield {
        "type": "diagram",
        "diagram_type": "free_body_diagram",
        "data": {
            "label": f"Euler Column  (K={K}, L={L} m)",
            "length": L,
            "forces": [
                {"label": f"Pcr={p_cr:.2f} N", "x": L / 2, "dx": 0, "dy": -1, "color": "#e74c3c"},
            ],
            "mode_shape": True,
        },
    }

    x    = np.linspace(0, L, 120)
    mode = np.sin(np.pi * x / max(L, 1e-6))
    yield {"type": "diagram", "diagram_type": "displacement_curve",
           "data": series_points(x, mode)}

    yield {
        "type": "final",
        "answer": "\n".join([
            "### Euler Column Buckling",
            r"Formula: $P_{cr} = \frac{\pi^2 EI}{(KL)^2}$",
            f"- Young's modulus ($E$): {E:.4e} Pa",
            f"- Second moment of area ($I$): {I:.6e} m⁴",
            f"- Column length ($L$): {L:.4f} m",
            f"- Effective length factor ($K$): {K:.4f}",
            f"- Effective length ($L_e = KL$): {Le:.4f} m",
            f"- Critical Euler load ($P_{{cr}}$): **{p_cr:.4f} N**",
        ]),
}
