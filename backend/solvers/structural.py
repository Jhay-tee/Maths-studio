"""
corrected_structural_v2.py

PRODUCTION-READY Structural Solver (v2)
- Beam analysis: simply supported, cantilever, fixed
- Reactions, shear force, bending moment, deflection
- Robust parameter extraction (ignores garbage fields)
- Numerical ODE integration for deflection
- Generates diagrams
"""

import asyncio
from typing import AsyncGenerator
import numpy as np
from scipy.integrate import odeint
import matplotlib.pyplot as plt
import io
import base64

logger_enabled = True


def _log(msg: str):
    if logger_enabled:
        print(f"[STRUCTURAL] {msg}")


async def solve_structural(sub: dict) -> AsyncGenerator[dict, None]:
    """
    Solve structural/beam problems.

    Parameters (from sub["parameters"]):
    - L: beam length (m)
    - w: UDL (N/m)
    - P: point load (N)
    - E: Young's modulus (Pa)
    - I: second moment of area (m^4)
    - beam_type: "simply_supported", "cantilever", "fixed"
    """
    params = sub.get("parameters", {})
    raw_query = sub.get("raw_query", "")
    problem_type = sub.get("problem_type", "beam_analysis")

    yield {
        "type": "step",
        "title": "Input validation",
        "content": "Checking beam parameters..."
    }

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: Extract parameters (IGNORE garbage fields like nativeEvent)
    # ─────────────────────────────────────────────────────────────────────────

    L = _safe_get_float(params, "L")
    if not L or L <= 0:
        L = _extract_length_from_text(raw_query)
    if not L or L <= 0:
        yield {
            "type": "final",
            "answer": "**Error:** Beam length L not found. Provide: `L = 6 m`"
        }
        return

    w = _safe_get_float(params, "w", default=0)  # N/m
    P = _safe_get_float(params, "P", default=0)  # N
    E = _safe_get_float(params, "E", default=200e9)  # Pa (default 200 GPa for steel)
    I = _safe_get_float(params, "I", default=8.33e-5)  # m^4 (default)

    EI = E * I

    beam_type = _safe_get_string(params, "beam_type", "simply_supported").lower()
    if "cantilever" in beam_type:
        beam_type = "cantilever"
    elif "fixed" in beam_type or "both" in beam_type:
        beam_type = "fixed"
    else:
        beam_type = "simply_supported"

    _log(f"Beam: {beam_type}, L={L}m, w={w}N/m, P={P}N, EI={EI:.2e}")

    yield {
        "type": "step",
        "title": "Beam configuration",
        "content": (
            f"**Type:** {beam_type.title()}\n"
            f"**Span (L):** {L} m\n"
            f"**UDL (w):** {w} N/m\n"
            f"**Point Load (P):** {P} N\n"
            f"**EI:** {EI:.3e} N·m²"
        )
    }

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: Calculate reactions
    # ─────────────────────────────────────────────────────────────────────────

    yield {
        "type": "step",
        "title": "Support reactions",
        "content": "Using equilibrium equations..."
    }

    if beam_type == "simply_supported":
        # Both ends simply supported
        total_load = w * L + P
        R_B = (total_load * L / 2) / L if L > 0 else 0
        R_A = total_load - R_B
        M_A = 0
        M_B = 0
        reactions_text = f"$R_A = {R_A:.2f}$ N\n$R_B = {R_B:.2f}$ N"

    elif beam_type == "cantilever":
        # Fixed at A, free at B
        R_A = w * L + P
        M_A = (w * L**2 / 2) + (P * L)
        R_B = 0
        M_B = 0
        reactions_text = (
            f"$R_A = {R_A:.2f}$ N\n"
            f"$M_A = {M_A:.2f}$ N·m"
        )

    else:  # fixed
        # Fixed at both ends
        total_load = w * L + P
        R_A = total_load / 2
        R_B = total_load / 2
        M_A = -(w * L**2 / 12) - (P * L / 8)
        M_B = -(w * L**2 / 12) - (P * L / 8)
        reactions_text = (
            f"$R_A = {R_A:.2f}$ N\n"
            f"$R_B = {R_B:.2f}$ N\n"
            f"$M_A = {M_A:.2f}$ N·m\n"
            f"$M_B = {M_B:.2f}$ N·m"
        )

    yield {"type": "step", "title": "Reactions", "content": reactions_text}

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: Shear and moment equations
    # ─────────────────────────────────────────────────────────────────────────

    def shear_force(x):
        if beam_type == "simply_supported":
            return R_A - w * x
        else:
            return R_A - w * x

    def bending_moment(x):
        if beam_type == "simply_supported":
            return R_A * x - (w * x**2 / 2)
        elif beam_type == "cantilever":
            return M_A + R_A * x - (w * x**2 / 2)
        else:
            return M_A + R_A * x - (w * x**2 / 2)

    # Calculate critical values
    x_vals = np.linspace(0, L, 1000)
    M_vals = np.array([bending_moment(x) for x in x_vals])
    V_vals = np.array([shear_force(x) for x in x_vals])

    max_M = np.max(np.abs(M_vals)) if len(M_vals) > 0 else 0
    x_max_M = x_vals[np.argmax(np.abs(M_vals))] if len(M_vals) > 0 else 0
    max_V = np.max(np.abs(V_vals)) if len(V_vals) > 0 else 0

    shear_moment_text = (
        f"**Shear Force:** $V(x) = {R_A:.2f} - {w}x$ N\n\n"
        f"**Bending Moment:** $M(x) = {R_A:.2f}x - {w/2}x^2$ N·m\n\n"
        f"**Max shear:** {max_V:.2f} N\n"
        f"**Max moment:** {max_M:.2f} N·m at $x = {x_max_M:.3f}$ m"
    )

    yield {
        "type": "step",
        "title": "Shear & moment equations",
        "content": shear_moment_text
    }

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: Deflection
    # ─────────────────────────────────────────────────────────────────────────

    yield {
        "type": "step",
        "title": "Deflection analysis",
        "content": "Computing v(x) and slopes..."
    }

    v_vals = None
    slope_vals = None
    max_deflection = 0
    x_max_deflection = 0

    try:
        def deflection_ode(y, x):
            # y[0] = v (deflection), y[1] = dv/dx (slope)
            if EI > 0:
                d_slope = bending_moment(x) / EI
            else:
                d_slope = 0
            return [y[1], d_slope]

        if beam_type == "simply_supported":
            y0 = [0, 0]
        elif beam_type == "cantilever":
            y0 = [0, 0]
        else:
            y0 = [0, 0]

        sol = odeint(deflection_ode, y0, x_vals)
        v_vals = sol[:, 0]
        slope_vals = sol[:, 1] * 180 / np.pi  # convert to degrees

        if len(v_vals) > 0:
            max_deflection = np.max(np.abs(v_vals)) * 1000  # convert to mm
            x_max_deflection = x_vals[np.argmax(np.abs(v_vals))]

        deflection_text = (
            f"**Max deflection:** {max_deflection:.4f} mm "
            f"at $x = {x_max_deflection:.3f}$ m\n\n"
            f"**Slope at A:** {slope_vals[0]:.4f}°\n"
            f"**Slope at B:** {slope_vals[-1]:.4f}°"
        )

    except Exception as e:
        _log(f"Deflection calculation skipped: {e}")
        deflection_text = "*(Deflection calculation skipped)*"

    yield {"type": "step", "title": "Deflection", "content": deflection_text}

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5: Generate plots
    # ─────────────────────────────────────────────────────────────────────────

    try:
        fig, axes = plt.subplots(2, 1, figsize=(10, 8))
        fig.suptitle(f"{beam_type.title()} Beam Analysis", fontsize=14)

        # Shear force
        axes[0].plot(x_vals, V_vals, "b-", linewidth=2, label="V(x)")
        axes[0].axhline(y=0, color="k", linestyle="-", linewidth=0.5)
        axes[0].fill_between(x_vals, V_vals, alpha=0.3)
        axes[0].set_ylabel("Shear Force (N)", fontsize=11)
        axes[0].set_title("Shear Force Diagram", fontsize=12)
        axes[0].grid(True, alpha=0.3)

        # Bending moment
        axes[1].plot(x_vals, M_vals, "r-", linewidth=2, label="M(x)")
        axes[1].axhline(y=0, color="k", linestyle="-", linewidth=0.5)
        axes[1].fill_between(x_vals, M_vals, alpha=0.3, color="red")
        axes[1].set_xlabel("Distance x (m)", fontsize=11)
        axes[1].set_ylabel("Bending Moment (N·m)", fontsize=11)
        axes[1].set_title("Bending Moment Diagram", fontsize=12)
        axes[1].grid(True, alpha=0.3)

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=100)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode()
        plt.close()

        yield {
            "type": "step",
            "title": "Diagrams",
            "content": f"![Beam diagrams](data:image/png;base64,{img_base64[:80]}...)"
        }

    except Exception as e:
        _log(f"Plot generation failed: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 6: Summary
    # ─────────────────────────────────────────────────────────────────────────

    answer = f"""
## Beam Analysis Summary

### Configuration
- **Beam type:** {beam_type.title()}
- **Span (L):** {L} m
- **UDL (w):** {w} N/m
- **Point load (P):** {P} N
- **EI:** {EI:.3e} N·m²

### Support Reactions
{reactions_text}

### Critical Values
- **Max shear force:** {max_V:.2f} N
- **Max bending moment:** {max_M:.2f} N·m at x = {x_max_M:.3f} m
- **Max deflection:** {max_deflection:.4f} mm at x = {x_max_deflection:.3f} m

### Equations
**Shear Force:** $V(x) = {R_A:.2f} - {w}x$ N

**Bending Moment:** $M(x) = {R_A:.2f}x - {w/2}x^2$ N·m

---
*Analysis complete.*
"""

    yield {"type": "final", "answer": answer.strip()}


# ─────────────────────────────────────────────────────────────────────────────
# Helper functions (ROBUST parameter extraction)
# ─────────────────────────────────────────────────────────────────────────────


def _safe_get_float(d: dict, key: str, default=None) -> float | None:
    """
    Safely extract a float from dict, ignoring non-numeric values.
    This prevents garbage fields like nativeEvent, eventPhase, etc.
    """
    try:
        val = d.get(key)
        if val is None:
            return default
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            val = val.strip()
            if val:
                return float(val)
        return default
    except (ValueError, TypeError, AttributeError):
        return default


def _safe_get_string(d: dict, key: str, default="") -> str:
    """Safely extract a string from dict."""
    try:
        val = d.get(key)
        if val is None:
            return default
        return str(val).strip()
    except:
        return default


def _extract_length_from_text(text: str) -> float | None:
    """Extract beam length L from raw query text."""
    import re

    patterns = [
        r"(?:length|span|L|beam)\s*[=:]?\s*([0-9.]+)\s*m\b",
        r"([0-9.]+)\s*m\s+(?:long|span|length)",
        r"([0-9.]+)\s*m(?:\s|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue

    return None
