"""
router.py  —  Two-layer hybrid classification engine.

Layer 1 : Deterministic keyword/pattern scorer   (zero I/O, O(n_tokens))
Layer 2 : Embedding nearest-neighbour            (optional, for unknown inputs)

Design principles
─────────────────
• Gemini is NEVER the classifier. It is a parameter extractor + explainer only.
• Layer 1 uses an inverted keyword index — O(1) lookup per token regardless of
  how many domains exist.  Adding a domain = adding one DomainRule entry.
• Confidence gating:  if L1 score < threshold OR two domains tie → escalate.
• Embedding upgrade path is built-in: swap _embed() and enable USE_EMBEDDINGS
  env var when you need to go beyond keyword rules.
• All public symbols used by main.py are at the bottom of this file.

v2 changes
──────────
• Added pre_extract() — domain-specific parameter pre-extraction that runs
  BEFORE Gemini, so algebra systems and structural problems arrive at the
  solver with clean, parser-ready data even when Gemini misbehaves.
• ClassificationResult now carries a `pre_extracted_params` dict that
  main.py merges into the Gemini output, giving L1 data priority.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Tuneable thresholds
# ─────────────────────────────────────────────────────────────────────────────
_CONFIDENCE_THRESHOLD = 0.50   # below this → escalate to Gemini full-route
_CONFLICT_MARGIN      = 0.10   # two domains within this margin → escalate
_PATTERN_WEIGHT_BOOST = 1.4    # regex match scores higher than plain keyword


# ─────────────────────────────────────────────────────────────────────────────
# Rule definition
# ─────────────────────────────────────────────────────────────────────────────

def _p(pat: str) -> re.Pattern:
    return re.compile(pat, re.IGNORECASE)


@dataclass
class DomainRule:
    """
    One domain entry.  All fields except `domain` are optional.

    problem_types  : sub-keyword → specific problem_type string.
                     The first sub-keyword found in the text wins.
    base_weight    : base confidence added when any signal fires.
    """
    domain:        str
    keywords:      list[str]              = field(default_factory=list)
    patterns:      list[re.Pattern]       = field(default_factory=list)
    problem_types: dict[str, str]         = field(default_factory=dict)
    base_weight:   float                  = 0.90
    description:   str                    = ""   # used for embedding fallback


# ─────────────────────────────────────────────────────────────────────────────
# Domain rule table
# ─────────────────────────────────────────────────────────────────────────────

DOMAIN_RULES: list[DomainRule] = [

    # ── Data visualisation ───────────────────────────────────────────────────
    DomainRule(
        domain="data_viz",
        description="Plotting, graphing, charting, data visualisation",
        keywords=[
            "plot", "graph", "chart", "visualise", "visualize", "draw a curve",
            "sketch", "surface plot", "histogram", "scatter", "bar chart",
            "pie chart", "heatmap", "draw the graph", "show the curve",
        ],
        patterns=[
            _p(r"\bplot\s+(of\s+)?[a-z0-9]"),
            _p(r"\bgraph\s+of\b"),
            _p(r"\bdraw\b.{0,25}\bcurve\b"),
            _p(r"\bsketch\b.{0,25}\b(graph|function|curve)\b"),
        ],
        problem_types={
            "scatter":   "scatter_plot",
            "bar":       "bar_chart",
            "histogram": "histogram",
            "surface":   "surface_plot",
            "pie":       "pie_chart",
            "heatmap":   "heatmap",
        },
        base_weight=0.97,
    ),

    # ── Algebra ──────────────────────────────────────────────────────────────
    DomainRule(
        domain="algebra",
        description="Equations, roots, factorisation, simultaneous systems",
        keywords=[
            "solve for", "find x", "find y", "find z", "roots of",
            "factorise", "factorize", "expand the bracket", "simplify",
            "simultaneous", "linear equation", "quadratic equation",
            "polynomial", "system of equations", "solve the equation",
            "algebraic", "solve algebraically",
        ],
        patterns=[
            _p(r"\bsolve\b.{0,40}="),
            _p(r"\broots?\s+of\b"),
            _p(r"\bfactor(ise|ize)\b"),
            _p(r"\bsolve\s+for\s+[a-z]\b"),
            _p(r"\bsimplif(y|ication)\b"),
            # Catches bare multi-line equation systems (3 or more variable equations)
            _p(r"[0-9][a-zA-Z]\s*[+\-]\s*[0-9][a-zA-Z]"),
        ],
        problem_types={
            "quadratic":     "quadratic_equation",
            "simultaneous":  "simultaneous_equations",
            "polynomial":    "polynomial_roots",
            "simplify":      "simplification",
            "expand":        "expansion",
            "linear":        "linear_equation",
        },
        base_weight=0.88,
    ),

    # ── Calculus ─────────────────────────────────────────────────────────────
    DomainRule(
        domain="calculus",
        description="Differentiation, integration, limits, ODEs, series",
        keywords=[
            "differentiate", "integrate", "derivative", "integral",
            "limit", "partial derivative", "gradient of", "divergence",
            "curl", "laplace transform", "fourier series", "taylor series",
            "maclaurin series", "differential equation", "ode", "pde",
            "rate of change", "second derivative", "antiderivative",
            "indefinite integral", "definite integral", "area under",
        ],
        patterns=[
            _p(r"\bd/d[a-z]\b"),
            _p(r"[∫\\]int\b"),
            _p(r"\blim\s*[_({\[]"),
            _p(r"\bdy/dx\b|\bdx/dt\b|\bdy/dt\b"),
            _p(r"\b∂[a-z]/∂[a-z]\b"),
            _p(r"\bd\^?2\s*y\s*/\s*dx\^?2\b"),
        ],
        problem_types={
            "derivative":          "differentiation",
            "differentiate":       "differentiation",
            "integral":            "integration",
            "integrate":           "integration",
            "area under":          "definite_integral",
            "limit":               "limit_evaluation",
            "taylor":              "taylor_series",
            "maclaurin":           "taylor_series",
            "laplace":             "laplace_transform",
            "fourier":             "fourier_series",
            "ode":                 "ode_solve",
            "differential equation": "ode_solve",
            "partial":             "partial_differentiation",
        },
        base_weight=0.94,
    ),

    # ── Mechanics ────────────────────────────────────────────────────────────
    DomainRule(
        domain="mechanics",
        description=(
            "Kinematics, dynamics, projectile motion, Newton's laws, "
            "friction, energy, vibration, rotation"
        ),
        keywords=[
            "projectile", "kinematics", "suvat", "velocity", "acceleration",
            "newton", "force", "momentum", "impulse", "friction",
            "normal force", "free body diagram", "torque", "angular velocity",
            "rotational inertia", "vibration", "oscillation", "spring constant",
            "simple harmonic motion", "shm", "work done", "kinetic energy",
            "potential energy", "collision", "centripetal", "circular motion",
            "equilibrium of forces", "coefficient of friction",
            "launches", "thrown", "fired", "range of projectile",
            "time of flight", "maximum height",
        ],
        patterns=[
            _p(r"\bv\s*=\s*u\s*\+\s*at\b"),
            _p(r"\bF\s*=\s*ma\b"),
            _p(r"\b(launch|fire|throw|project)ed?\b"),
            _p(r"\bangle\s+of\s+(projection|launch|elevation|inclination)\b"),
            _p(r"\binitial\s+(velocity|speed)\b"),
            _p(r"\bhorizontal\s+range\b"),
            _p(r"\bcoefficient\s+of\s+(static|kinetic|dynamic)?\s*friction\b"),
        ],
        problem_types={
            "projectile":           "projectile_motion",
            "kinematics":           "kinematics",
            "suvat":                "kinematics",
            "time of flight":       "projectile_motion",
            "maximum height":       "projectile_motion",
            "range":                "projectile_motion",
            "vibration":            "vibrations",
            "oscillation":          "vibrations",
            "spring":               "vibrations",
            "shm":                  "vibrations",
            "simple harmonic":      "vibrations",
            "rotation":             "rotation",
            "torque":               "rotation",
            "angular":              "rotation",
            "friction":             "contact_forces",
            "normal force":         "contact_forces",
            "equilibrium":          "statics",
            "work done":            "work_energy",
            "kinetic energy":       "work_energy",
            "potential energy":     "work_energy",
            "collision":            "collision",
            "momentum":             "collision",
            "circular":             "circular_motion",
            "centripetal":          "circular_motion",
        },
        base_weight=0.92,
    ),

    # ── Structural ───────────────────────────────────────────────────────────
    DomainRule(
        domain="structural",
        description=(
            "Beam analysis, trusses, deflection, bending moment, "
            "shear force, stress, strain"
        ),
        keywords=[
            "beam", "cantilever", "simply supported", "truss", "frame",
            "column", "deflection", "bending moment", "shear force",
            "reaction force", "point load", "udl", "distributed load",
            "moment of inertia", "second moment of area", "cross section",
            "virtual work", "moment area", "slope of beam",
            "axial load", "buckling", "euler load", "fixed end beam",
            "overhanging beam", "continuous beam", "macaulay",
            "flexural rigidity", "ei", "neutral axis",
            "stress", "strain", "young's modulus", "modulus of elasticity",
        ],
        patterns=[
            _p(r"\b(simply\s+supported|cantilever|fixed[\s-]end)\s+beam\b"),
            _p(r"\b(deflection|slope)\s+at\b"),
            _p(r"\budl\b|\buniformly\s+distributed\s+load\b"),
            _p(r"\bbending\s+moment\b|\bshear\s+force\b"),
            _p(r"\bEI\s*d\^?2\b|\bEI\b"),
            _p(r"\bpoint\s+load\b"),
        ],
        problem_types={
            "cantilever":          "cantilever_beam",
            "simply supported":    "simply_supported_beam",
            "fixed end":           "fixed_beam",
            "truss":               "truss_analysis",
            "deflection":          "beam_deflection",
            "buckling":            "column_buckling",
            "axial":               "axial_loading",
            "virtual work":        "virtual_work",
            "bending moment":      "bending_moment",
            "shear force":         "shear_force",
            "stress":              "stress_strain",
            "strain":              "stress_strain",
        },
        base_weight=0.95,
    ),

    # ── Fluids ───────────────────────────────────────────────────────────────
    DomainRule(
        domain="fluids",
        description=(
            "Fluid mechanics, flow rate, Bernoulli, pipe flow, "
            "hydrostatics, buoyancy, Reynolds number"
        ),
        keywords=[
            "fluid", "flow rate", "bernoulli", "continuity equation",
            "pipe flow", "reynolds number", "viscosity", "pressure drop",
            "hydrostatic", "hydrostatics", "buoyancy", "archimedes",
            "density of water", "venturi", "orifice", "manometer",
            "hydraulic", "laminar", "turbulent", "darcy", "friction factor",
            "head loss", "discharge", "volumetric flow", "mass flow",
            "streamline", "stagnation pressure", "dynamic pressure",
        ],
        patterns=[
            _p(r"\bQ\s*=\s*A\s*v\b"),
            _p(r"\bbernoulli\b"),
            _p(r"\breynolds\s*(number)?\b"),
            _p(r"\bflow\s+(rate|velocity|through|in\s+pipe)\b"),
            _p(r"\bpressure\s+at\s+the\s+(bottom|depth)\b"),
            _p(r"\bbuoyan(cy|t)\b"),
        ],
        problem_types={
            "bernoulli":      "bernoulli_equation",
            "continuity":     "continuity_equation",
            "hydrostatic":    "hydrostatics",
            "buoyancy":       "buoyancy",
            "archimedes":     "buoyancy",
            "reynolds":       "reynolds_number",
            "venturi":        "venturi_meter",
            "pipe flow":      "pipe_flow",
            "head loss":      "pipe_flow",
            "discharge":      "flow_rate",
        },
        base_weight=0.93,
    ),

    # ── Thermodynamics ───────────────────────────────────────────────────────
    DomainRule(
        domain="thermo",
        description=(
            "Heat transfer, thermodynamic cycles, gas laws, "
            "entropy, enthalpy, conduction, convection"
        ),
        keywords=[
            "temperature", "heat transfer", "entropy", "enthalpy",
            "carnot cycle", "ideal gas", "gas law", "boyle's law",
            "charles' law", "specific heat", "thermal conductivity",
            "conduction", "convection", "radiation heat",
            "rankine cycle", "brayton cycle", "refrigeration", "cop",
            "heat engine", "first law of thermodynamics",
            "second law of thermodynamics", "internal energy",
            "isothermal", "adiabatic", "isobaric", "isochoric",
            "heat capacity", "specific heat capacity",
        ],
        patterns=[
            _p(r"\bPV\s*=\s*nRT\b|\bPV\s*=\s*mRT\b"),
            _p(r"\bheat\s+(engine|pump|exchanger|sink|source)\b"),
            _p(r"\bcarnot\b"),
            _p(r"\bideal\s+gas\b"),
            _p(r"\bQ\s*=\s*mc\b|\bQ\s*=\s*mc[Δd]T\b"),
            _p(r"\b(isothermal|adiabatic|isobaric|isochoric)\b"),
        ],
        problem_types={
            "carnot":          "carnot_cycle",
            "ideal gas":       "ideal_gas_law",
            "boyle":           "ideal_gas_law",
            "charles":         "ideal_gas_law",
            "conduction":      "heat_conduction",
            "convection":      "heat_convection",
            "rankine":         "rankine_cycle",
            "brayton":         "brayton_cycle",
            "entropy":         "entropy",
            "enthalpy":        "enthalpy",
            "specific heat":   "specific_heat",
        },
        base_weight=0.92,
    ),

    # ── Circuits ─────────────────────────────────────────────────────────────
    DomainRule(
        domain="circuits",
        description=(
            "Electrical circuits, Ohm's law, KVL, KCL, "
            "resistors, capacitors, inductors, AC/DC"
        ),
        keywords=[
            "resistor", "capacitor", "inductor", "ohm's law",
            "kirchhoff", "kvl", "kcl", "voltage divider", "current divider",
            "series circuit", "parallel circuit", "thevenin", "norton",
            "superposition theorem", "impedance", "reactance", "power factor",
            "rc circuit", "rl circuit", "rlc circuit", "ac circuit", "dc circuit",
            "diode", "transistor", "op-amp", "amplifier", "electric current",
            "electric voltage", "resistance", "conductance",
        ],
        patterns=[
            _p(r"\bV\s*=\s*IR\b"),
            _p(r"\b(kvl|kcl)\b"),
            _p(r"\bthevenin\b|\bnorton\b"),
            _p(r"\bimpedance\b"),
            _p(r"\b\d+\s*[kKmMgG]?[Ωω]\b"),
            _p(r"\b\d+\s*[kKmM]?[Vv]\s+and\s+\d+"),
        ],
        problem_types={
            "ohm":          "ohms_law",
            "kvl":          "kvl_analysis",
            "kcl":          "kcl_analysis",
            "thevenin":     "thevenin_equivalent",
            "norton":       "norton_equivalent",
            "rc":           "rc_circuit",
            "rlc":          "rlc_circuit",
            "power factor": "ac_power",
        },
        base_weight=0.93,
    ),

    # ── Physics (optics, waves, modern) ──────────────────────────────────────
    DomainRule(
        domain="physics",
        description=(
            "Optics, wave mechanics, Doppler effect, "
            "refraction, interference, modern physics"
        ),
        keywords=[
            "snell's law", "refraction", "reflection", "optics",
            "wavelength", "wave speed", "doppler effect",
            "speed of light", "refractive index", "critical angle",
            "total internal reflection", "interference", "diffraction",
            "photoelectric effect", "de broglie", "bohr model",
            "nuclear decay", "half life", "radioactive",
            "electromagnetic wave", "photon", "quantum",
        ],
        patterns=[
            _p(r"\bsnell\b"),
            _p(r"\bn_?1\s*sin|\bn_?2\s*sin\b"),
            _p(r"\bdoppler\b"),
            _p(r"\brefractive\s+index\b"),
            _p(r"\btotal\s+internal\s+reflection\b"),
            _p(r"\bhalf[\s-]life\b"),
        ],
        problem_types={
            "snell":                   "snells_law",
            "refraction":              "snells_law",
            "total internal":          "total_internal_reflection",
            "doppler":                 "doppler_effect",
            "wavelength":              "wave_mechanics",
            "diffraction":             "diffraction",
            "photoelectric":           "photoelectric_effect",
            "half life":               "radioactive_decay",
            "de broglie":              "de_broglie",
        },
        base_weight=0.93,
    ),

    # ── Control systems ──────────────────────────────────────────────────────
    DomainRule(
        domain="controls",
        description=(
            "Control systems, transfer functions, Bode plots, "
            "stability, PID, root locus, state space"
        ),
        keywords=[
            "transfer function", "bode plot", "root locus",
            "pid controller", "step response", "impulse response",
            "closed loop", "open loop", "gain margin",
            "phase margin", "nyquist", "state space",
            "controllability", "observability", "steady state error",
            "overshoot", "settling time", "rise time",
            "feedback control", "proportional integral derivative",
        ],
        patterns=[
            _p(r"\bG\s*\(\s*s\s*\)"),
            _p(r"\bH\s*\(\s*s\s*\)"),
            _p(r"\bpoles?\s+(at|of)\b"),
            _p(r"\bzeros?\s+(at|of)\b"),
            _p(r"\bbode\s+plot\b"),
            _p(r"\bs\^?2\s*\+.{0,20}s\b"),
        ],
        problem_types={
            "bode":          "bode_plot",
            "root locus":    "root_locus",
            "pid":           "pid_design",
            "step response": "step_response",
            "stability":     "stability_analysis",
            "state space":   "state_space",
            "nyquist":       "nyquist_plot",
        },
        base_weight=0.95,
    ),

    # ── Statistics ───────────────────────────────────────────────────────────
    DomainRule(
        domain="statistics",
        description=(
            "Statistics, probability, distributions, hypothesis testing, "
            "regression, confidence intervals"
        ),
        keywords=[
            "mean", "median", "mode", "standard deviation", "variance",
            "confidence interval", "hypothesis test", "p-value",
            "t-test", "chi-square", "regression", "correlation",
            "normal distribution", "binomial distribution", "poisson",
            "probability", "sample size", "z-score", "anova",
            "f-test", "pearson", "spearman", "skewness", "kurtosis",
            "statistical significance", "null hypothesis",
        ],
        patterns=[
            _p(r"\bstd\s*dev\b|\bstandard\s+deviation\b"),
            _p(r"\bconfidence\s+interval\b"),
            _p(r"\bt[\s-]?test\b"),
            _p(r"\bchi[\s-]?square\b"),
            _p(r"\bp[\s-]?value\b"),
            _p(r"\bnull\s+hypothesis\b"),
        ],
        problem_types={
            "regression":        "linear_regression",
            "correlation":       "correlation_analysis",
            "t-test":            "hypothesis_test",
            "chi-square":        "chi_square_test",
            "anova":             "anova",
            "confidence":        "confidence_interval",
            "normal":            "normal_distribution",
            "binomial":          "binomial_distribution",
            "poisson":           "poisson_distribution",
        },
        base_weight=0.92,
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Inverted keyword index  (built once at import time)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _IndexEntry:
    rule:   DomainRule
    weight: float


_KEYWORD_INDEX: dict[str, list[_IndexEntry]] = {}

for _rule in DOMAIN_RULES:
    for _kw in _rule.keywords:
        _key = _kw.lower().strip()
        _KEYWORD_INDEX.setdefault(_key, []).append(
            _IndexEntry(rule=_rule, weight=_rule.base_weight)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Public result type
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    domain:               str
    problem_type:         str
    confidence:           float
    matched_signals:      list[str]         # for logging / debug
    pre_extracted_params: dict              = field(default_factory=dict)
    """
    Parameters that L1 extracted deterministically (e.g. algebra equations).
    main.py merges these INTO the Gemini-extracted params so that clean
    L1 data always wins over potentially mangled Gemini data.
    """


# ─────────────────────────────────────────────────────────────────────────────
# Domain-specific pre-extractors
# These run INSIDE fast_classify, before Gemini ever sees the input.
# They produce clean, solver-ready params that bypass Gemini's extraction.
# ─────────────────────────────────────────────────────────────────────────────

# Matches one equation line: optional label like "1)" or "eq1:" then math
_EQ_LINE_RE = re.compile(
    r"(?:^|\n)\s*(?:\d+[\)\.:]|eq\s*\d*\s*:?)?\s*"   # optional label
    r"([A-Za-z0-9][^=\n]*=[^=\n][^\n]*)",              # LHS = RHS
    re.IGNORECASE,
)

# Detects bare implicit-multiplication: "3x", "4y", "2z"
_IMPLICIT_MUL_RE = re.compile(r"(\d)([A-Za-z])")

# English prose markers — if expression contains these it's not pure math
_PROSE_RE = re.compile(
    r"\b(solve|find|calculate|determine|what|the\s+equation|"
    r"three|variables|given|such|where|linear|system)\b",
    re.IGNORECASE,
)


def _normalize_equation(eq: str) -> str:
    """
    Turn a human-written equation into a SymPy-ready string.

    '3x + 4y - 2z = 12'  →  '3*x + 4*y - 2*z - 12'
    """
    eq = eq.strip()
    if "=" in eq:
        lhs, rhs = eq.split("=", 1)
        # Move RHS to left: LHS - RHS
        rhs = rhs.strip()
        lhs = lhs.strip()
        # Handle negative RHS gracefully
        if rhs.startswith("-"):
            expr = f"({lhs}) + ({rhs})"
        else:
            expr = f"({lhs}) - ({rhs})"
    else:
        expr = eq

    # Insert explicit multiplication: 3x → 3*x
    expr = _IMPLICIT_MUL_RE.sub(r"\1*\2", expr)
    return expr.strip()


def _pre_extract_algebra(text: str) -> dict:
    """
    Extract equation systems directly from the raw user text.
    Returns {"equations": [...], "problem_type_hint": "..."}
    or {} if nothing parseable found.
    """
    lines = re.split(r"[\n;]|(?<=[0-9])\s*\)\s*(?=[0-9A-Za-z])", text)
    equations = []
    for line in lines:
        line = line.strip()
        # Must contain a letter (variable), an operator, and an equals sign
        if not re.search(r"[A-Za-z]", line):
            continue
        if "=" not in line:
            continue
        # Reject pure English sentences
        if _PROSE_RE.search(line) and not re.search(r"\d", line):
            continue
        # Must look like math (has digit or operator around the =)
        if not re.search(r"[\d+\-*/^]", line):
            continue
        equations.append(_normalize_equation(line))

    if not equations:
        return {}

    hint = "simultaneous_equations" if len(equations) > 1 else "linear_equation"
    return {"equations": equations, "problem_type_hint": hint}


def _pre_extract_structural(text: str) -> dict:
    """
    Extract the most common structural parameters from plain English.
    Returns a partial params dict; missing keys will be filled by Gemini.
    """
    params: dict = {}
    lowered = text.lower()

    # Span / length
    m = re.search(r"(?:length|span|beam)\s+(?:of\s+)?([0-9.]+)\s*(m|cm|mm)\b", lowered)
    if m:
        val = float(m.group(1))
        unit = m.group(2)
        if unit == "cm":  val /= 100
        elif unit == "mm": val /= 1000
        params["L"] = val

    # UDL
    m = re.search(r"([0-9.]+)\s*(kn|n)\s*/\s*m\b", lowered)
    if m:
        val = float(m.group(1))
        if "kn" in m.group(2).lower(): val *= 1000
        params["w"] = val

    # Point load
    m = re.search(r"(?:point\s+load|concentrated\s+load)\s+(?:of\s+)?([0-9.]+)\s*(kn|n)\b", lowered)
    if m:
        val = float(m.group(1))
        if "kn" in m.group(2).lower(): val *= 1000
        params["P"] = val

    # Beam type
    if re.search(r"simply\s+supported", lowered):
        params["beam_type"] = "simply_supported"
    elif re.search(r"cantilever", lowered):
        params["beam_type"] = "cantilever"
    elif re.search(r"fixed[\s-]end|fixed\s+beam", lowered):
        params["beam_type"] = "fixed"

    return params


# Domain → pre-extractor function
_PRE_EXTRACTORS = {
    "algebra":    _pre_extract_algebra,
    "structural": _pre_extract_structural,
}


# ─────────────────────────────────────────────────────────────────────────────
# Core classifier
# ─────────────────────────────────────────────────────────────────────────────

def _score(text: str) -> dict[str, float]:
    """Return raw domain scores for *text* (lowercased)."""
    scores: dict[str, float] = {}

    # ── Keyword pass (O(n_unique_keywords) at worst, O(1) average) ──────────
    for kw, entries in _KEYWORD_INDEX.items():
        if kw in text:
            for entry in entries:
                d = entry.rule.domain
                scores[d] = scores.get(d, 0.0) + entry.weight

    # ── Regex pass (only rules that define patterns) ──────────────────────
    for rule in DOMAIN_RULES:
        for pat in rule.patterns:
            if pat.search(text):
                d = rule.domain
                scores[d] = scores.get(d, 0.0) + rule.base_weight * _PATTERN_WEIGHT_BOOST

    return scores


def _infer_problem_type(domain: str, text: str) -> str:
    for rule in DOMAIN_RULES:
        if rule.domain != domain:
            continue
        for sub_kw, pt in rule.problem_types.items():
            if sub_kw in text:
                return pt
        return f"{domain}_general"
    return "general"


def fast_classify(text: str) -> Optional[ClassificationResult]:
    """
    Layer-1 deterministic classification.

    Returns ClassificationResult when confident, None when uncertain
    (caller should escalate to Gemini for full extraction).

    If a domain-specific pre-extractor fires, the result carries
    `pre_extracted_params` so main.py can skip or correct Gemini output.
    """
    if not text or not text.strip():
        return None

    lowered = text.lower()
    scores  = _score(lowered)

    if not scores:
        return None

    total  = sum(scores.values()) or 1.0
    norm   = {d: v / total for d, v in scores.items()}
    ranked = sorted(norm.items(), key=lambda x: x[1], reverse=True)

    best_domain, best_score = ranked[0]

    # Low confidence → escalate
    if best_score < _CONFIDENCE_THRESHOLD:
        logger.debug(f"L1 low confidence ({best_score:.2f}) — escalating: {text[:60]}")
        return None

    # Two domains too close → escalate
    if len(ranked) > 1 and (best_score - ranked[1][1]) < _CONFLICT_MARGIN:
        logger.debug(
            f"L1 conflict ({best_domain}={best_score:.2f} vs "
            f"{ranked[1][0]}={ranked[1][1]:.2f}) — escalating"
        )
        return None

    # Collect matched signals for logging
    signals = []
    for kw, entries in _KEYWORD_INDEX.items():
        if kw in lowered and any(e.rule.domain == best_domain for e in entries):
            signals.append(kw)
    for rule in DOMAIN_RULES:
        if rule.domain != best_domain:
            continue
        for pat in rule.patterns:
            m = pat.search(lowered)
            if m:
                signals.append(m.group(0))

    # ── Domain-specific pre-extraction ───────────────────────────────────────
    pre_params: dict = {}
    extractor = _PRE_EXTRACTORS.get(best_domain)
    if extractor:
        try:
            pre_params = extractor(text)  # use original text, not lowered
            if pre_params:
                logger.info(
                    f"L1 pre-extracted {len(pre_params)} param(s) "
                    f"for domain={best_domain}: {list(pre_params.keys())}"
                )
        except Exception as exc:
            logger.warning(f"Pre-extractor failed for {best_domain}: {exc}")

    # Use pre-extracted problem_type_hint if available
    problem_type = pre_params.pop("problem_type_hint", None) or \
                   _infer_problem_type(best_domain, lowered)

    return ClassificationResult(
        domain=best_domain,
        problem_type=problem_type,
        confidence=round(best_score, 3),
        matched_signals=signals[:10],
        pre_extracted_params=pre_params,
)
