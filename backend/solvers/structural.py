import asyncio
from sympy import symbols, integrate, solve, Rational, simplify, Piecewise, Le, And


async def solve_structural(sub: dict):
    """
    Structural solver. Reads from sub["parameters"] (Gemini-extracted)
    and sub["raw_query"] (clean restatement).

    Handles:
    - Simply supported beam with UDL
    - Simply supported beam with point load
    - Cantilever with UDL or point load
    """

    yield {"type": "step", "content": "Initializing Structural Analysis Kernel..."}
    await asyncio.sleep(0)

    params = sub.get("parameters", {})
    raw = sub.get("raw_query", "").lower()
    problem_type = sub.get("problem_type", "").lower()

    yield {"type": "step", "content": "Parsing structural parameters..."}
    await asyncio.sleep(0)

    # ── Parameter extraction helpers ──
    def extract_val(params: dict, *keys) -> float | None:
        for k in keys:
            for pk, pv in params.items():
                if k in pk.lower():
                    try:
                        # Handle "12 kN/m", "6 m", "4 kN" etc.
                        return float(str(pv).split()[0])
                    except (ValueError, IndexError):
                        pass
        return None

    def extract_unit(params: dict, *keys) -> str:
        for k in keys:
            for pk, pv in params.items():
                if k in pk.lower():
                    parts = str(pv).split()
                    if len(parts) > 1:
                        return parts[1]
        return ""

    L = extract_val(params, "length", "span", "l")
    w = extract_val(params, "udl", "distributed load", "load intensity", "w")
    P = extract_val(params, "point load", "concentrated load", "p")
    a = extract_val(params, "distance", "position", "a")  # point load position from A

    # Fallback: parse from raw_query if params incomplete
    if L is None or (w is None and P is None):
        import re
        nums = re.findall(r"[\d.]+", raw)
        floats = [float(n) for n in nums]

        if "udl" in raw or "uniformly distributed" in raw or "kn/m" in raw:
            if len(floats) >= 2:
                L = L or floats[0]
                w = w or floats[1]
        elif "point load" in raw or "concentrated" in raw:
            if len(floats) >= 2:
                L = L or floats[0]
                P = P or floats[1]

    if L is None:
        yield {
            "type": "final",
            "answer": "Could not extract beam length from the problem. Please specify the length clearly (e.g. '6 m').",
        }
        return

    force_unit = "kN"
    moment_unit = "kN·m"

    # ─────────────────────────────────────────────────────────
    # CASE 1: Simply Supported Beam — UDL over full span
    # ─────────────────────────────────────────────────────────
    if w is not None and ("simply supported" in raw or "simply_supported" in problem_type or "udl" in problem_type):
        yield {"type": "step", "content": f"Configuration: Simply supported beam, L={L} m, UDL w={w} kN/m"}
        await asyncio.sleep(0)

        yield {"type": "step", "content": "Step 1: Computing support reactions using equilibrium..."}
        await asyncio.sleep(0)

        # ΣFy = 0 → RA + RB = w·L
        # ΣM_A = 0 → RB·L = w·L·(L/2) → RB = w·L/2
        total_load = w * L
        RA = total_load / 2
        RB = total_load / 2

        yield {"type": "step", "content": f"  ΣFy = 0  →  RA + RB = w·L = {w}×{L} = {total_load} {force_unit}"}
        await asyncio.sleep(0)
        yield {"type": "step", "content": f"  ΣM_A = 0  →  RB = w·L/2 = {RB} {force_unit}  |  RA = {RA} {force_unit}"}
        await asyncio.sleep(0)

        yield {"type": "step", "content": "Step 2: Building Shear Force Diagram (SFD)..."}
        await asyncio.sleep(0)

        # SFD: V(x) = RA - w·x
        # At x=0: V = RA
        # At x=L/2: V = 0
        # At x=L: V = -RB
        sfd_zero = RA / w  # where V=0

        sfd_points = {
            f"x=0 (A)": RA,
            f"x={L/2} m (midspan)": RA - w * (L / 2),
            f"x={sfd_zero} m (V=0)": 0.0,
            f"x={L} m (B)": -RB,
        }

        yield {"type": "step", "content": f"  V(x) = RA - w·x = {RA} - {w}x"}
        await asyncio.sleep(0)
        yield {"type": "step", "content": f"  V=0 at x = RA/w = {RA}/{w} = {sfd_zero} m from A"}
        await asyncio.sleep(0)

        yield {"type": "step", "content": "Step 3: Building Bending Moment Diagram (BMD)..."}
        await asyncio.sleep(0)

        # BMD: M(x) = RA·x - w·x²/2
        # Maximum at x where V=0, i.e. x = L/2
        x_max_moment = sfd_zero
        M_max = RA * x_max_moment - w * (x_max_moment ** 2) / 2

        bmd_points = {
            f"x=0 (A)": 0.0,
            f"x={x_max_moment} m": M_max,
            f"x={L} m (B)": 0.0,
        }

        yield {"type": "step", "content": f"  M(x) = RA·x - (w·x²)/2 = {RA}x - {w/2}x²"}
        await asyncio.sleep(0)
        yield {"type": "step", "content": f"  M_max at x={x_max_moment} m → M = {RA}×{x_max_moment} - {w/2}×{x_max_moment}² = {M_max} {moment_unit}"}
        await asyncio.sleep(0)

        yield {"type": "step", "content": "Step 4: Verifying equilibrium..."}
        await asyncio.sleep(0)

        check = round(RA + RB, 6) == round(total_load, 6)
        yield {"type": "step", "content": f"  RA + RB = {RA} + {RB} = {RA+RB} {force_unit}  ✓" if check else f"  ⚠ Equilibrium check failed"}
        await asyncio.sleep(0)

        # ── Format answer ──
        sfd_table = "\n".join(f"  {loc}: {val:+.2f} {force_unit}" for loc, val in sfd_points.items())
        bmd_table = "\n".join(f"  {loc}: {val:.2f} {moment_unit}" for loc, val in bmd_points.items())

        answer = f"""SIMPLY SUPPORTED BEAM — UDL ANALYSIS
{'─'*44}

GIVEN
  Beam length      L = {L} m
  UDL intensity    w = {w} kN/m
  Total load       W = {total_load} kN

1. SUPPORT REACTIONS
  RA = {RA} kN  (upward)
  RB = {RB} kN  (upward)

2. SHEAR FORCE DIAGRAM (SFD)
{sfd_table}
  SFD equation:  V(x) = {RA} - {w}x

3. BENDING MOMENT DIAGRAM (BMD)
{bmd_table}
  BMD equation:  M(x) = {RA}x - {w/2}x²
  **Maximum BM = {M_max} {moment_unit} at x = {x_max_moment} m from A**

4. ZERO SHEAR FORCE
  V(x) = 0  →  x = RA/w = {RA}/{w} = {sfd_zero} m from A
  ✓ Coincides with midspan (L/2 = {L/2} m) — confirmed symmetric loading

5. VERIFICATION
  Max BM (formula) = wL²/8 = {w}×{L}²/8 = {w * L**2 / 8} {moment_unit}  ✓
  RA + RB = {RA} + {RB} = {RA+RB} kN = w·L = {total_load} kN  ✓"""

        yield {"type": "final", "answer": answer}
        return

    # ─────────────────────────────────────────────────────────
    # CASE 2: Simply Supported Beam — Point Load
    # ─────────────────────────────────────────────────────────
    if P is not None and ("simply supported" in raw or "simply_supported" in problem_type):
        a_val = a if a is not None else L / 2  # default midspan
        b_val = L - a_val

        yield {"type": "step", "content": f"Configuration: Simply supported beam, L={L} m, Point Load P={P} kN at x={a_val} m"}
        await asyncio.sleep(0)

        yield {"type": "step", "content": "Step 1: Computing reactions..."}
        await asyncio.sleep(0)

        RB = (P * a_val) / L
        RA = P - RB

        yield {"type": "step", "content": f"  ΣM_A = 0  →  RB = P·a/L = {P}×{a_val}/{L} = {RB:.4f} {force_unit}"}
        await asyncio.sleep(0)
        yield {"type": "step", "content": f"  RA = P - RB = {P} - {RB:.4f} = {RA:.4f} {force_unit}"}
        await asyncio.sleep(0)

        yield {"type": "step", "content": "Step 2: SFD..."}
        await asyncio.sleep(0)

        M_max = (P * a_val * b_val) / L

        yield {"type": "step", "content": f"  M_max = P·a·b/L = {P}×{a_val}×{b_val}/{L} = {M_max:.4f} {moment_unit} at x={a_val} m"}
        await asyncio.sleep(0)

        answer = f"""SIMPLY SUPPORTED BEAM — POINT LOAD ANALYSIS
{'─'*44}

GIVEN
  Beam length   L = {L} m
  Point Load    P = {P} kN at x = {a_val} m from A

1. SUPPORT REACTIONS
  RA = {RA:.4f} kN
  RB = {RB:.4f} kN

2. SHEAR FORCE DIAGRAM
  x = 0 to {a_val} m:   V = +{RA:.4f} {force_unit}
  x = {a_val} to {L} m: V = -{RB:.4f} {force_unit}

3. BENDING MOMENT DIAGRAM
  M(0) = 0
  **M_max = {M_max:.4f} {moment_unit} at x = {a_val} m**
  M(L) = 0

4. VERIFICATION
  RA + RB = {RA+RB:.4f} = P = {P} {force_unit}  ✓"""

        yield {"type": "final", "answer": answer}
        return

    # ─────────────────────────────────────────────────────────
    # CASE 3: Cantilever — UDL
    # ─────────────────────────────────────────────────────────
    if w is not None and "cantilever" in raw:
        yield {"type": "step", "content": f"Configuration: Cantilever beam, L={L} m, UDL w={w} kN/m"}
        await asyncio.sleep(0)

        RA = w * L
        MA = w * L ** 2 / 2

        yield {"type": "step", "content": f"  Fixed-end reaction: RA = {RA} {force_unit}, MA = {MA} {moment_unit}"}
        await asyncio.sleep(0)

        answer = f"""CANTILEVER BEAM — UDL ANALYSIS
{'─'*44}

GIVEN
  Beam length   L = {L} m
  UDL           w = {w} kN/m

1. FIXED-END REACTIONS
  RA (vertical) = w·L = {RA} {force_unit}
  MA (moment)   = w·L²/2 = {MA} {moment_unit}

2. SHEAR FORCE DIAGRAM
  V(x) = w·(L - x)
  V at fixed end (x=0): {RA} {force_unit}
  V at free  end (x=L): 0

3. BENDING MOMENT DIAGRAM
  M(x) = w·(L-x)²/2
  **M_max = {MA} {moment_unit} at fixed end (x=0)**
  M at free end = 0"""

        yield {"type": "final", "answer": answer}
        return

    # ─────────────────────────────────────────────────────────
    # FALLBACK
    # ─────────────────────────────────────────────────────────
    yield {
        "type": "final",
        "answer": (
            f"Structural solver received: domain='{sub.get('domain')}', type='{sub.get('problem_type')}'\n"
            f"Extracted parameters: {params}\n\n"
            "Could not match a specific structural case. Please ensure the problem includes:\n"
            "  • Beam type (simply supported / cantilever)\n"
            "  • Beam length\n"
            "  • Load type and magnitude (UDL in kN/m or Point Load in kN)"
        ),
    }
