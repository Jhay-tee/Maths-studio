import re
import sympy as sp

def clean_math_string(s):
    """
    Strips common natural language words often left by LLM or user.
    """
    if not s: return ""
    
    # Common prefixes to strip
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
        r"equation[:\s]*",
        r"expression[:\s]*",
    ]
    
    clean = s.strip()
    # Remove surrounding quotes if model added them
    if (clean.startswith("'") and clean.endswith("'")) or (clean.startswith('"') and clean.endswith('"')):
        clean = clean[1:-1]
        
    for p in prefixes:
        clean = re.sub(p, "", clean, flags=re.IGNORECASE).strip()
        
    # If "y = f(x) from x=... to x=..."
    # We want to stop at "from"
    if " from " in clean.lower():
        clean = re.split(r"\s+from\s+", clean, flags=re.IGNORECASE)[0].strip()
        
    return clean

def safe_sympify(expr_str, symbols=None):
    """
    Wraps sp.sympify with robust cleaning.
    """
    clean = clean_math_string(expr_str)
    try:
        return sp.sympify(clean, locals=symbols)
    except Exception as e:
        # Fallback: if it's "x = 5", just return 5 or something? 
        # No, let the solver handle it.
        raise e

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
