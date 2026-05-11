import numpy as np
import sympy as sp
import asyncio
from solvers.constants import STEEL_YOUNGS_MODULUS, STEEL_DENSITY, G

async def solve_structural(sub: dict):
    params = sub.get("parameters", {})
    raw = sub.get("raw_query", "").lower()
    
    # ROUTING LOGIC: Determine the most efficient method
    if params.get("nodes") and params.get("members"):
        # Use FEM for complex meshes/frames
        async for chunk in solve_fem_frame(params): yield chunk
    elif "mohr" in raw or "principal" in raw:
        async for chunk in solve_mohrs_circle(params): yield chunk
    else:
        # Use Advanced Singularity Solver for general beams
        async for chunk in solve_beam_advanced(params, raw): yield chunk

async def solve_beam_advanced(params, raw):
    yield {"type": "step", "content": "Analyzing beam using Singularity Functions (Macaulay's Method)..."}

    # 1. Parameter Normalization
    L = float(params.get("l", 6))
    E = float(params.get("e", 200e9))
    I = float(params.get("i", 1e-4))
    
    # Support for multiple loads
    point_loads = params.get("point_loads", []) # Expected: [{"P": 1000, "a": 2}]
    if not point_loads and params.get("p"): 
        point_loads = [{"P": float(params.get("p")), "a": float(params.get("a", L/2))}]
    
    udls = params.get("udls", []) # Expected: [{"w": 500, "start": 0, "end": 6}]
    if not udls and params.get("w"):
        udls = [{"w": float(params.get("w")), "start": 0, "end": L}]

    # 2. Static Equilibrium (Solve for Reactions RA, RB)
    # Sum of Moments at A = 0 => RB*L - sum(P*a) - sum(w*len*dist) = 0
    total_moment_about_a = 0
    total_vertical_load = 0
    
    for load in point_loads:
        total_moment_about_a += load['P'] * load['a']
        total_vertical_load += load['P']
        
    for load in udls:
        load_mag = load['w'] * (load['end'] - load['start'])
        centroid = (load['start'] + load['end']) / 2
        total_moment_about_a += load_mag * centroid
        total_vertical_load += load_mag

    # Support types
    is_cantilever = "cantilever" in raw or params.get("type") == "cantilever"
    
    if is_cantilever:
        RA = total_vertical_load
        MA = total_moment_about_a
        RB = 0
    else:
        RB = total_moment_about_a / L
        RA = total_vertical_load - RB
        MA = 0

    # Calculate reactions first and yield step
    yield {"type": "step", "content": f"Calculating support reactions using equilibrium equations..."}

    # 3. Singularity (Macaulay) Functions
    def macaulay(x, a, n):
        return np.where(x >= a, (x - a)**n, 0)

    def get_shear(x):
        v = RA * macaulay(x, 0, 0)
        for load in point_loads:
            v -= load['P'] * macaulay(x, load['a'], 0)
        for load in udls:
            v -= load['w'] * (macaulay(x, load['start'], 1) - macaulay(x, load['end'], 1))
        return v

    def get_moment(x):
        m = RA * macaulay(x, 0, 1) - MA * macaulay(x, 0, 0)
        for load in point_loads:
            m -= load['P'] * macaulay(x, load['a'], 1)
        for load in udls:
            m -= (load['w'] / 2) * (macaulay(x, load['start'], 2) - macaulay(x, load['end'], 2))
        return m

    # Yield step for shear/moment calculation
    yield {"type": "step", "content": "Computing shear force and bending moment diagrams..."}

    # 4. Numerical Evaluation
    x_range = np.linspace(0, L, 501)
    v_vals = get_shear(x_range)
    m_vals = get_moment(x_range)
    
    max_m = np.max(np.abs(m_vals))
    max_v = np.max(np.abs(v_vals))

    # Yield step for deflection
    yield {"type": "step", "content": "Computing deflection profile using double integration (M/EI method)..."}

    # 5. Deflection (Integration Approximation)
    # Double integration of M/EI. Using trapezoidal rule for general cases.
    slope = np.cumsum(m_vals) * (L/500) / (E * I)
    # Adjust slope for boundary conditions (e.g., slope at wall=0 for cantilever)
    if is_cantilever:
        slope -= slope[0]
    else:
        # Simply supported: integration constant makes deflection at ends = 0
        pass 
    
    deflection = np.cumsum(slope) * (L/500)
    if not is_cantilever:
        # Correct deflection so y(0)=0 and y(L)=0
        deflection -= np.linspace(deflection[0], deflection[-1], 501)
    
    max_delta = np.max(np.abs(deflection))

    # 6. Formatting Output
    steps = [
        "### Universal Beam Analysis Report",
        f"**Method:** Singularity Functions (Macaulay's Method)",
        f"**Configuration:** {'Cantilever' if is_cantilever else 'Simply Supported'}",
        "---",
        "#### 1. Support Reactions",
        f"- **$R_A$ (Left):** {RA:,.2f} N",
        f"- **$R_B$ (Right):** {RB:,.2f} N" if not is_cantilever else f"- **$M_A$ (Moment):** {MA:,.2f} Nm",
        "",
        "#### 2. Maximum Internal Forces",
        f"- **Max Shear ($V_{{max}}$):** {max_v:,.2f} N",
        f"- **Max Moment ($M_{{max}}$):** {max_m:,.2f} Nm",
        f"- **Max Deflection ($\delta_{{max}}$):** {max_delta*1000:.4f} mm",
        "",
        "#### 3. Stress Distribution Table",
        "| Position (m) | Shear (N) | Moment (Nm) |",
        "|:---:|:---:|:---:|",
    ]

    # Add critical points to table
    crit_pts = sorted(list(set([0, L, L/2] + [l['a'] for l in point_loads])))
    for pt in crit_pts:
        v_pt = get_shear(np.array([pt]))[0]
        m_pt = get_moment(np.array([pt]))[0]
        steps.append(f"| {pt:.2f} | {v_pt:,.2f} | {m_pt:,.2f} |")

    # Emit shear and moment diagrams
    diagram_data = {
        "x": x_range.tolist(),
        "shear": v_vals.tolist(),
        "moment": m_vals.tolist(),
        "length": L,
        "max_shear": float(max_v),
        "max_moment": float(max_m),
        "max_deflection": float(max_delta),
        "type": "cantilever" if is_cantilever else "simply_supported"
    }
    yield {"type": "diagram", "diagram_type": "beam_analysis", "data": diagram_data}
    yield {"type": "final", "answer": "\n".join(steps)}

# Note: solve_fem_frame and solve_mohrs_circle remain as in your original snippet.
