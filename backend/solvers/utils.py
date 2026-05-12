import re
import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor,
)

MATH_TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)

def clean_math_string(s):
    """
    Strips common natural language words often left by LLM or user.
    Handles lists by joining with semi-colons.
    """
    if s is None: return ""
    
    if isinstance(s, list):
        # Join with a distinct separator
        s = " ; ".join(str(item) for item in s)
    
    # Common prefixes to strip - expanded to catch common LLM boilerplate
    prefixes = [
        r"solve (the )?(linear |quadratic )?equation",
        r"calculate (the )?",
        r"find (the )?",
        r"evaluate (the )?",
        r"determine (the )?",
        r"compute (the )?",
        r"differentiate (the )?",
        r"integrate (the )?",
        r"plot (the )?",
        r"what is (the )?",
        r"result in",
        r"equation(s?)[:\s]*",
        r"expression(s?)[:\s]*",
        r"solution(s?)[:\s]*",
        r"result(s?)[:\s]*",
        r"answer(s?)[:\s]*",
        r"ans[:\s]*",
        r"symbolic solution[:\s]*",
        r"step-by-step solution[:\s]*",
    ]
    
    clean = str(s).strip()
    # Remove surrounding quotes or backticks if model added them
    if (clean.startswith("'") and clean.endswith("'")) or (clean.startswith('"') and clean.endswith('"')) or (clean.startswith('`') and clean.endswith('`')):
        clean = clean[1:-1]
        
    for p in prefixes:
        # Use word boundaries and ignore case
        p_pattern = r"^\s*" + p
        clean = re.sub(p_pattern, "", clean, flags=re.IGNORECASE).strip()
        
    # Remove common boilerplate at the end
    clean = re.split(r"\s+and\s+solve", clean, flags=re.IGNORECASE)[0]
    clean = re.split(r"\s+and\s+plot", clean, flags=re.IGNORECASE)[0]
    
    # If "y = f(x) from x=... to x=..."
    # We want to stop at "from"
    if " from " in clean.lower():
        clean = re.split(r"\s+from\s+", clean, flags=re.IGNORECASE)[0].strip()
        
    return clean.strip()

def safe_sympify(expr_str, symbols=None):
    """
    Wraps sp.sympify with robust cleaning.
    """
    clean = clean_math_string(expr_str)
    locals_dict = dict(symbols or {})

    # Detect variable names and add to locals if not present
    for name in set(re.findall(r"[A-Za-z_]\w*", clean)):
        if name not in locals_dict:
            locals_dict[name] = sp.Symbol(name)

    try:
        # First attempt with simplifying enabled for cleaner internal representation
        parsed = parse_expr(clean, local_dict=locals_dict, transformations=MATH_TRANSFORMATIONS, evaluate=True)
        return parsed
    except Exception:
        # Fallback to standard sympify
        try:
            return sp.sympify(clean, locals=locals_dict)
        except Exception:
            # Last ditch effort: if it's a list or similar, just return as is or error
            return sp.sympify(clean)

def simplify_math(expr):
    """
    Symbolically simplifies an expression using SymPy.
    """
    if expr is None: return None
    try:
        if isinstance(expr, str):
            expr = safe_sympify(expr)
        return sp.simplify(expr)
    except Exception:
        return expr

def detect_variables(expr):
    """
    Returns a list of free symbols in an expression.
    """
    if expr is None: return []
    try:
        if isinstance(expr, str):
            expr = safe_sympify(expr)
        return sorted([s.name for s in expr.free_symbols])
    except Exception:
        return []

def validate_physical_params(params, constraints=None):
    """
    Checks parameters against physical constraints (e.g. mass > 0).
    Returns (is_valid, error_msg)
    """
    if not params: return True, None
    
    # Standard physical constraints
    standard_constraints = {
        "m": {"min": 0, "label": "Mass"},
        "mass": {"min": 0, "label": "Mass"},
        "L": {"min": 0, "label": "Length"},
        "l": {"min": 0, "label": "Length"},
        "k": {"min": 0, "label": "Stiffness"},
        "T": {"min": 0, "label": "Absolute Temperature", "unit": "K"}, # Assume K if not specified? 
        "rho": {"min": 0, "label": "Density"},
    }
    
    # Merge with custom constraints
    if constraints:
        standard_constraints.update(constraints)
        
    for key, val in params.items():
        if key in standard_constraints:
            limit = standard_constraints[key]
            try:
                numeric_val = float(val)
                if "min" in limit and numeric_val < limit["min"]:
                    return False, f"{limit['label']} ({key}) cannot be less than {limit['min']}{limit.get('unit', '')}."
                if "max" in limit and numeric_val > limit["max"]:
                    return False, f"{limit['label']} ({key}) exceeds physical limit of {limit['max']}{limit.get('unit', '')}."
            except (ValueError, TypeError):
                continue
                
    return True, None

def normalize_params(params):
    """
    Normalizes common physics/engineering parameter names to standard keys.
    """
    if not params: return {}
    
    # Map of lowercase synonyms to standard keys
    mapping = {
        "initial velocity": "u",
        "initial_velocity": "u",
        "v1": "u",
        "final velocity": "v",
        "final_velocity": "v",
        "v2": "v",
        "acceleration": "a",
        "time": "t",
        "displacement": "s",
        "distance": "s",
        "mass": "m",
        "force": "F",
        "point load": "P",
        "point_load": "P",
        "distributed load": "w",
        "distributed_load": "w",
        "vertical load": "P",
        "gravity": "g",
        "length": "L",
        "width": "w",
        "height": "h",
        "depth": "d",
        "diameter": "D",
        "radius": "r",
        "density": "rho",
        "pressure": "P",
        "temperature": "T",
        "volume": "V",
        "energy": "E",
        "work": "W",
        "power": "P_out",
        "stiffness": "k",
        "spring constant": "k",
        "angle": "theta",
        "theta": "theta",
        "frequency": "f",
        "period": "T_period",
        "angular velocity": "omega",
        "torque": "tau",
    }
    
    normalized = {}
    for k, v in params.items():
        # Preserve original
        normalized[k] = v
        
        k_clean = k.lower().replace("_", " ")
        if k_clean in mapping:
            normalized[mapping[k_clean]] = v
            
    return normalized


STANDARD_DEFAULTS = {
    "g": 9.81,
    "rho": 1000.0,
    "n1": 1.0,
    "n2": 1.5,
    "f": 50.0,
    "E": 200e9,
    "I": 1e-4,
}


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def apply_standard_defaults(params):
    enriched = dict(params or {})
    for key, value in STANDARD_DEFAULTS.items():
        if enriched.get(key) in (None, ""):
            enriched[key] = value
    return enriched


def merge_params(*param_sets):
    merged = {}
    for param_set in param_sets:
        if not param_set:
            continue
        for key, value in param_set.items():
            if value not in (None, ""):
                merged[key] = value
    return normalize_params(merged)


def find_missing_params(domain, problem_type, params, raw_query=""):
    lowered_query = (raw_query or "").lower()
    lowered_type = (problem_type or "").lower()
    lowered_domain = (domain or "").lower()
    normalized = apply_standard_defaults(normalize_params(params or {}))

    def require(spec):
        missing = []
        for item in spec:
            key = item["key"]
            aliases = item.get("aliases", [])
            found = normalized.get(key)
            if found in (None, ""):
                for alias in aliases:
                    if normalized.get(alias) not in (None, ""):
                        found = normalized.get(alias)
                        break
            if found in (None, ""):
                missing.append(item)
        return missing

    if lowered_domain == "mechanics" and ("projectile" in lowered_type or "projectile" in lowered_query):
        return require([
            {"key": "v0", "aliases": ["velocity"], "label": "Initial velocity", "unit": "m/s", "hint": "Example: 20"},
            {"key": "theta", "aliases": ["angle"], "label": "Launch angle", "unit": "deg", "hint": "Example: 45"},
        ])

    if lowered_domain == "mechanics" and ("kinematics" in lowered_type or "motion" in lowered_query):
        known = sum(1 for key in ["u", "v", "a", "t", "s"] if normalized.get(key) not in (None, ""))
        if known < 3:
            return [
                {"key": "u", "label": "Initial velocity", "unit": "m/s", "hint": "Any 3 of u, v, a, t, s are enough."},
                {"key": "v", "label": "Final velocity", "unit": "m/s"},
                {"key": "a", "label": "Acceleration", "unit": "m/s²"},
                {"key": "t", "label": "Time", "unit": "s"},
                {"key": "s", "label": "Displacement", "unit": "m"},
            ]

    if lowered_domain == "circuits" and ("ohm" in lowered_query or "resistance" in lowered_query or "ohms_law" in lowered_type):
        known = sum(1 for key in ["v", "i", "r"] if normalized.get(key) not in (None, ""))
        if known < 2:
            return [
                {"key": "v", "label": "Voltage", "unit": "V", "hint": "Provide any 2 of V, I, R."},
                {"key": "i", "label": "Current", "unit": "A"},
                {"key": "r", "label": "Resistance", "unit": "Ohm"},
            ]

    if lowered_domain == "fluids" and ("continuity" in lowered_query or "continuity" in lowered_type):
        known = sum(1 for key in ["v1", "v2", "a1", "a2"] if normalized.get(key) not in (None, ""))
        if known < 3:
            return [
                {"key": "v1", "label": "Inlet velocity", "unit": "m/s"},
                {"key": "v2", "label": "Outlet velocity", "unit": "m/s"},
                {"key": "a1", "label": "Inlet area", "unit": "m²"},
                {"key": "a2", "label": "Outlet area", "unit": "m²"},
            ]

    if lowered_domain == "structural" and any(keyword in lowered_type or keyword in lowered_query for keyword in ["beam", "deflection", "shear", "moment"]):
        return require([
            {"key": "L", "aliases": ["l"], "label": "Beam length", "unit": "m", "hint": "Total span length."},
        ])

    if lowered_domain == "statistics":
        raw_numbers = re.findall(r"[-+]?\d*\.\d+|\d+", lowered_query)
        values = normalized.get("data", [])
        if not values and len(raw_numbers) < 2:
            return [
                {"key": "data", "label": "Dataset", "unit": "comma-separated", "hint": "Example: 12, 15, 18, 20"},
            ]

    return []


def parse_user_supplied_value(raw_value):
    if isinstance(raw_value, (int, float, list, dict)):
        return raw_value
    if raw_value is None:
        return None

    text = str(raw_value).strip()
    if not text:
        return None

    if "," in text and not any(ch in text for ch in "[]{}"):
        numbers = [segment.strip() for segment in text.split(",") if segment.strip()]
        parsed_numbers = [_to_float(item) for item in numbers]
        if all(item is not None for item in parsed_numbers):
            return parsed_numbers

    numeric_value = _to_float(text)
    if numeric_value is not None:
        return numeric_value

    return text


def parse_numeric_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        parsed = []
        for item in value:
            maybe = _to_float(item)
            if maybe is not None:
                parsed.append(maybe)
        return parsed

    text = str(value).strip()
    if not text:
        return []


def resolve_numeric_expressions(params):
    resolved = dict(params or {})

    def looks_numeric_expression(value):
        if not isinstance(value, str):
            return False
        text = value.strip()
        if not text or len(text) > 80:
            return False
        if re.search(r"[=,]", text):
            return False
        if re.search(r"[+\-*/^()]", text) or re.search(r"\d", text):
            return True
        return False

    numeric_locals = {}
    for key, value in resolved.items():
        try:
            numeric_locals[key] = float(value)
        except (TypeError, ValueError):
            continue

    def transform(value):
        if isinstance(value, dict):
            return {inner_key: transform(inner_value) for inner_key, inner_value in value.items()}
        if isinstance(value, list):
            return [transform(item) for item in value]
        if not looks_numeric_expression(value):
            return value
        try:
            expr = safe_sympify(value, symbols=numeric_locals)
            if getattr(expr, "free_symbols", None) and expr.free_symbols:
                return value
            return float(expr)
        except Exception:
            return value

    for key, value in list(resolved.items()):
        new_value = transform(value)
        resolved[key] = new_value
        try:
            numeric_locals[key] = float(new_value)
        except (TypeError, ValueError):
            continue

    return resolved


def polish_final_answer(answer, domain="", problem_type=""):
    text = (answer or "").strip()
    if not text:
        return text

    if "###" not in text:
        heading = "### Solution"
        if domain:
            heading = f"### {domain.replace('_', ' ').title()} Solution"
        text = f"{heading}\n{text}"

    text = text.replace("\n- **", "\n- **").replace("\n\n\n", "\n\n")
    return text.strip()

    text = text.strip("[]()")
    parts = [segment.strip() for segment in re.split(r"[,\s]+", text) if segment.strip()]
    values = []
    for part in parts:
        maybe = _to_float(part)
        if maybe is not None:
            values.append(maybe)
    return values
