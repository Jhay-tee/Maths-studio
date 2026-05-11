import asyncio
import numpy as np
import sympy as sp
import logging

logger = logging.getLogger(__name__)

async def solve_structural(sub: dict):
    yield {"type": "step", "content": "Initializing Advanced FEM Kernel..."}
    
    params = sub.get("parameters", {})
    pt = sub.get("problem_type", "").lower()
    raw = sub.get("raw_query", "").lower()
    
    if "mohr" in raw or "stress" in pt and "principal" in raw:
        async for chunk in solve_mohrs_circle(params):
            yield chunk
    elif "centroid" in pt or "inertia" in raw or "section" in pt:
        async for chunk in solve_section_properties(params):
            yield chunk
    elif "truss" in pt or "truss" in raw:
        async for chunk in solve_fem_truss(params):
            yield chunk
    elif ("frame" in pt or "frame" in raw or "beam" in pt or "beam" in raw or "deflection" in raw) and params.get("nodes"):
        async for chunk in solve_fem_frame(params):
            yield chunk
    elif "virtual_work" in pt or "virtual work" in raw:
        async for chunk in solve_virtual_work(params):
            yield chunk
    elif "moment_area" in pt or "moment area" in raw:
        async for chunk in solve_moment_area(params):
            yield chunk
    else:
        async for chunk in solve_beam(params, raw):
            yield chunk

async def solve_fem_truss(params):
    yield {"type": "step", "content": "Assembling Global Stiffness Matrix for Truss..."}
    
    nodes = params.get("nodes", []) 
    members = params.get("members", []) 
    loads = params.get("loads", [])
    
    if not nodes or not members:
        yield {"type": "final", "answer": "Error: Truss analysis requires structured node (coord, BC) and member (E, A, connect) data."}
        return

    n_nodes = len(nodes)
    n_dof = 2 * n_nodes
    K_global = np.zeros((n_dof, n_dof))
    
    for member in members:
        node_i = nodes[member['from']]
        node_j = nodes[member['to']]
        
        L = np.sqrt((node_j['x'] - node_i['x'])**2 + (node_j['y'] - node_i['y'])**2)
        c = (node_j['x'] - node_i['x']) / L
        s = (node_j['y'] - node_i['y']) / L
        
        E = member.get('E', 210e9) 
        A = member.get('A', 0.005) 
        
        k_local_const = (E * A) / L
        k_local = k_local_const * np.array([
            [c*c, c*s, -c*c, -c*s],
            [c*s, s*s, -c*s, -s*s],
            [-c*c, -c*s, c*c, c*s],
            [-c*s, -s*s, c*s, s*s]
        ])
        
        dofs = [2*member['from'], 2*member['from']+1, 2*member['to'], 2*member['to']+1]
        for ii in range(4):
            for jj in range(4):
                K_global[dofs[ii], dofs[jj]] += k_local[ii, jj]

    yield {"type": "step", "content": f"Global matrix assembled ({n_dof}x{n_dof}). Applying Boundary Conditions..."}
    
    F = np.zeros(n_dof)
    for load in loads:
        node_idx = load['node']
        F[2*node_idx] += load.get('fx', 0)
        F[2*node_idx+1] += load.get('fy', 0)
        
    fixed_dofs = []
    for node in nodes:
        bc = node.get('bc', [0, 0])
        if bc[0] == 1: fixed_dofs.append(2*node['id'])
        if bc[1] == 1: fixed_dofs.append(2*node['id']+1)
        
    free_dofs = [i for i in range(n_dof) if i not in fixed_dofs]
    K_red = K_global[np.ix_(free_dofs, free_dofs)]
    F_red = F[free_dofs]
    
    yield {"type": "step", "content": "Solving system: [K]{u} = {F}..."}
    
    try:
        u_red = np.linalg.solve(K_red, F_red)
        u_full = np.zeros(n_dof)
        u_full[free_dofs] = u_red
        
        reactions = K_global @ u_full - F
        
        steps = [
            "### Truss FEM Analysis Report",
            "- **Element Type:** 2D Linear Truss Element",
            "- **Solver Type:** Direct Gaussian Elimination",
            "#### Results Summary",
            "| Node | $\Delta x$ (mm) | $\Delta y$ (mm) | $R_x$ (kN) | $R_y$ (kN) |",
            "|---|---|---|---|---|",
        ]
        
        for n in nodes:
            dx = u_full[2*n['id']] * 1000
            dy = u_full[2*n['id']+1] * 1000
            rx = reactions[2*n['id']] / 1000
            ry = reactions[2*n['id']+1] / 1000
            steps.append(f"| {n['id']} | {dx:.4f} | {dy:.4f} | {rx:.4f} | {ry:.4f} |")
            
        yield {"type": "final", "answer": "\n".join(steps)}
        
    except Exception as e:
        yield {"type": "final", "answer": f"FEM Solver Error: Singular matrix detected. {str(e)}"}

async def solve_fem_frame(params):
    yield {"type": "step", "content": "Initializing 2D Frame Solver (Euler-Bernoulli Beam-Column)..."}
    
    nodes = params.get("nodes", []) 
    members = params.get("members", []) 
    loads = params.get("loads", [])
    
    if not nodes or not members:
        yield {"type": "final", "answer": "Error: Frame/Beam analysis requires node coordinates, member connectivity, and section properties."}
        return

    n_nodes = len(nodes)
    n_dof = 3 * n_nodes
    K_global = np.zeros((n_dof, n_dof))
    
    for member in members:
        i, j = member['from'], member['to']
        ni, nj = nodes[i], nodes[j]
        L = np.sqrt((nj['x']-ni['x'])**2 + (nj['y']-ni['y'])**2)
        c = (nj['x']-ni['x'])/L
        s = (nj['y']-ni['y'])/L
        E, A, I = member.get('E', 210e9), member.get('A', 0.005), member.get('I', 1e-4)
        kp = np.array([
            [ E*A/L, 0, 0, -E*A/L, 0, 0 ],
            [ 0, 12*E*I/L**3, 6*E*I/L**2, 0, -12*E*I/L**3, 6*E*I/L**2 ],
            [ 0, 6*E*I/L**2, 4*E*I/L, 0, -6*E*I/L**2, 2*E*I/L ],
            [-E*A/L, 0, 0, E*A/L, 0, 0 ],
            [ 0, -12*E*I/L**3, -6*E*I/L**2, 0, 12*E*I/L**3, -6*E*I/L**2 ],
            [ 0, 6*E*I/L**2, 2*E*I/L, 0, -6*E*I/L**2, 4*E*I/L ]
        ])
        T = np.array([
            [c, s, 0, 0, 0, 0],
            [-s, c, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0],
            [0, 0, 0, c, s, 0],
            [0, 0, 0, -s, c, 0],
            [0, 0, 0, 0, 0, 1]
        ])
        ke = T.T @ kp @ T
        dofs = [3*i, 3*i+1, 3*i+2, 3*j, 3*j+1, 3*j+2]
        for ii in range(6):
            for jj in range(6): K_global[dofs[ii], dofs[jj]] += ke[ii, jj]

    F = np.zeros(n_dof)
    for load in loads:
        idx = load['node']
        F[3*idx] += load.get('fx', 0)
        F[3*idx+1] += load.get('fy', 0)
        F[3*idx+2] += load.get('mz', 0)
            
    fixed_dofs = []
    for n in nodes:
        bc = n.get('bc', [0,0,0])
        for idx, val in enumerate(bc):
            if val == 1: fixed_dofs.append(3*n['id'] + idx)
            
    free_dofs = [k for k in range(n_dof) if k not in fixed_dofs]
    K_red = K_global[np.ix_(free_dofs, free_dofs)]
    u_red = np.linalg.solve(K_red, F[free_dofs])
    u_full = np.zeros(n_dof)
    u_full[free_dofs] = u_red
        
    steps = [
        "### Frame FEM Analysis Report",
        "#### Nodal Displacements",
        "| ID | $\Delta x$ (mm) | $\Delta y$ (mm) | $\\theta_z$ (rad) |",
        "|---|---|---|---|",
    ]
    for n in nodes:
        dx, dy, rz = u_full[3*n['id']]*1000, u_full[3*n['id']+1]*1000, u_full[3*n['id']+2]
        steps.append(f"| {n['id']} | {dx:.3f} | {dy:.3f} | {rz:.6f} |")
            
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_virtual_work(params):
    yield {"type": "step", "content": "Calculating Virtual Work Integral..."}
    x = sp.Symbol('x')
    L = float(params.get("L", 5))
    E = float(params.get("E", 200e9))
    I = float(params.get("I", 1e-4))
    P = float(params.get("P", 1000)) # Virtual unit load or real load

    # Example: Cantilever with point load at end
    M = -P * (L - x)
    m = -1 * (L - x) # Unit load at end
    
    delta = sp.integrate((M * m) / (E * I), (x, 0, L))
    
    steps = [
        "### Virtual Work Solution",
        "**Equation:** $\\delta = \\int_0^L \\frac{M m}{EI} dx$",
        f"**Parameters:** $L={L}$m, $E={E/1e9}$GPa, $I={I}$m$^4$, $P={P}$N",
        f"**Bending Moment (Real):** $M(x) = {sp.latex(M)}$",
        f"**Bending Moment (Virtual):** $m(x) = {sp.latex(m)}$",
        "#### Calculated Result",
        f"- **Deflection:** $\\delta = {float(delta)*1000:.4f}$ mm"
    ]
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_moment_area(params):
    yield {"type": "step", "content": "Initializing Moment-Area Analysis..."}
    x = sp.Symbol('x')
    
    L = float(params.get("L", 5))
    E = float(params.get("E", 200e9))
    I = float(params.get("I", 1e-4))
    P = float(params.get("P", 1000))

    M = -P * (L - x)
    # Area under M/EI
    theta = sp.integrate(M / (E * I), (x, 0, L))
    # Moment of area under M/EI about end B (x=L)
    t = sp.integrate((M / (E * I)) * (L - x), (x, 0, L))

    steps = [
        "### Moment-Area Method Report",
        "**Theorem 1:** $\\theta_{B/A} = \\int_A^B \\frac{M}{EI} dx$",
        "**Theorem 2:** $t_{B/A} = \\int_A^B \\frac{M}{EI} x dx$",
        "#### Integration Results",
        f"**Moment Function:** $M(x) = {sp.latex(M)}$",
        f"- **Change in Slope ($\Delta \\theta$):** {float(theta):.6f} rad",
        f"- **Tangential Deviation ($t$):** {float(t)*1000:.4f} mm"
    ]
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_mohrs_circle(params):
    yield {"type": "step", "content": "Executing Stress State Transformation (Mohr's Circle)..."}
    sx = float(params.get("sx", params.get("sigma_x", 0)))
    sy = float(params.get("sy", params.get("sigma_y", 0)))
    txy = float(params.get("txy", params.get("tau_xy", 0)))
    
    avg_stress = (sx + sy) / 2
    r = np.sqrt(((sx - sy) / 2)**2 + txy**2)
    s1 = avg_stress + r
    s2 = avg_stress - r
    tmax = r
    
    # Principle angle
    theta_p = 0.5 * np.degrees(np.arctan2(2 * txy, sx - sy))
    
    steps = [
        "### Mohr's Circle: Principal Stress Analysis",
        f"**Input State:** $\\sigma_x = {sx}, \\sigma_y = {sy}, \\tau_{{xy}} = {txy}$",
        "#### Calculated Results",
        f"- **Average Stress (Center):** {avg_stress:.2f}",
        f"- **Principal Stress 1 ($\\sigma_1$):** {s1:.2f}",
        f"- **Principal Stress 2 ($\\sigma_2$):** {s2:.2f}",
        f"- **Maximum Shear Stress ($\\tau_{{max}}$):** {tmax:.2f}",
        f"- **Principal Plane Angle ($\\theta_{{p1}}$):** {theta_p:.2f}$^\\circ$"
    ]
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_beam(params, raw):
    yield {"type": "step", "content": "Analyzing Beam Deflection, Shear, and Bending Moments..."}
    # Lowercase keys for robust lookup
    p_low = {k.lower(): v for k, v in params.items()}
    l = float(p_low.get("l", 5)) # Length
    e = float(p_low.get("e", 200e9)) # Modulus (Steel)
    i = float(p_low.get("i", 1e-4)) # Inertia
    p = float(p_low.get("p", 1000)) # Point Load
    w = float(p_low.get("w", 0))    # Distributed Load
    
    steps = [f"### Euler-Bernoulli Beam Analysis"]
    
    points = [0, l/4, l/2, 3*l/4, l]
    moment_values = []
    shear_values = []
    
    # Simple Cases
    if "cantilever" in raw:
        support = "Cantilever (Fixed-Free)"
        if w > 0:
            delta_max = (w * l**4) / (8 * e * i)
            m_max = (w * l**2) / 2
            v_max = w * l
            # Equations: x=0 is fixed, x=l is free
            for x in points:
                # M(x) = -w(L-x)^2 / 2
                moment_values.append(-w * (l-x)**2 / 2)
                # V(x) = w(L-x)
                shear_values.append(w * (l-x))
            steps.append(f"**Load:** Distributed load $w = {w}$ N/m")
        else:
            delta_max = (p * l**3) / (3 * e * i)
            m_max = p * l
            v_max = p
            for x in points:
                # M(x) = -P(L-x)
                moment_values.append(-p * (l-x))
                shear_values.append(p)
            steps.append(f"**Load:** Point load $P = {p}$ N at end")
    else: # Simply Supported
        support = "Simply Supported (Pin-Roller)"
        if w > 0:
            delta_max = (5 * w * l**4) / (384 * e * i)
            m_max = (w * l**2) / 8
            v_max = (w * l) / 2
            for x in points:
                # M(x) = (wLx - wx^2)/2
                moment_values.append((w*l*x - w*x**2)/2)
                # V(x) = w(L/2 - x)
                shear_values.append(w*(l/2 - x))
            steps.append(f"**Load:** Uniformly Distributed Load $w = {w}$ N/m")
        else:
            delta_max = (p * l**3) / (48 * e * i)
            m_max = (p * l) / 4
            v_max = p / 2
            for x in points:
                # M(x) for x <= L/2 = Px/2
                # M(x) for x > L/2 = P(L-x)/2
                m_x = (p * x / 2) if x <= l/2 else (p * (l-x) / 2)
                moment_values.append(m_x)
                # V(x) = P/2 for x < L/2, -P/2 for x > L/2
                v_x = p/2 if x < l/2 else (-p/2 if x > l/2 else 0)
                shear_values.append(v_x)
            steps.append(f"**Load:** Concentrated load $P = {p}$ N at midspan")
        
    steps.extend([
        f"**Configuration:** {support}",
        f"**Geometric Info:** $L={l}$m, $E={e/1e9:.1f}$GPa, $I={i:.2e}$m$^4$",
        "#### Summary of Calculated Extrema",
        f"- **Max Deflection ($\\delta_{{max}}$):** {delta_max*1000:.4f} mm",
        f"- **Max Bending Moment ($M_{{max}}$):** {m_max/1000:.2f} kNm",
        f"- **Max Shear Force ($V_{{max}}$):** {v_max/1000:.2f} kN",
        "#### Discretized Internal Forces",
        "| Position (x/L) | Moment (kNm) | Shear (kN) |",
        "|---|---|---|",
    ])
    
    for i_pt, x in enumerate(points):
        x_label = ["0", "L/4", "L/2", "3L/4", "L"][i_pt]
        steps.append(f"| {x_label} | {moment_values[i_pt]/1000:.2f} | {shear_values[i_pt]/1000:.2f} |")
        
    steps.append("\n*Note: Use the diagram visualization for detailed curves.*")
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_section_properties(params):
    yield {"type": "step", "content": "Calculating Geometric Section Properties..."}
    
    # Expected format: list of shapes (e.g. rectangles)
    # shapes: [{"type": "rect", "b": 10, "h": 20, "x": 0, "y": 0}]
    shapes = params.get("shapes", [])
    if not shapes:
        # Fallback to simple I-beam or Rect if possible from raw
        yield {"type": "final", "answer": "Please provide section geometry (e.g. I-beam dimensions, Rectangular width/height) for property calculation."}
        return

    total_area = 0
    sum_ay = 0
    sum_ax = 0
    
    for s in shapes:
        if s['type'] == 'rect':
            area = s['b'] * s['h']
            total_area += area
            sum_ax += area * (s['x'] + s['b']/2)
            sum_ay += area * (s['y'] + s['h']/2)
            
    if total_area == 0:
        yield {"type": "final", "answer": "Error: Total area is zero. Check your dimensions."}
        return

    centroid_x = sum_ax / total_area
    centroid_y = sum_ay / total_area
    
    ixx = 0
    iyy = 0
    for s in shapes:
        if s['type'] == 'rect':
            b, h = s['b'], s['h']
            dy = (s['y'] + h/2) - centroid_y
            dx = (s['x'] + b/2) - centroid_x
            # Parallel Axis Theorem: I = I_local + Ad^2
            ixx += (b * h**3 / 12) + (b * h * dy**2)
            iyy += (h * b**3 / 12) + (b * h * dx**2)

    steps = [
        "### Sectional Properties Analysis",
        f"- **Total Area ($A$):** {total_area:.2f} units$^2$",
        f"- **Centroid ($\bar{{x}}, \bar{{y}}$):** ({centroid_x:.2f}, {centroid_y:.2f})",
        f"- **Moment of Inertia ($I_{{xx}}$):** {ixx:.2e} units$^4$",
        f"- **Moment of Inertia ($I_{{yy}}$):** {iyy:.2e} units$^4$",
        f"- **Radius of Gyration ($r_x$):** {np.sqrt(ixx/total_area):.2f} units"
    ]
    
    yield {"type": "final", "answer": "\n".join(steps)}
