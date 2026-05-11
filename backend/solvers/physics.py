import asyncio
import numpy as np

async def solve_physics(data):
    yield {"type": "step", "content": "Initializing Universal Physics Kernel..."}
    
    params = data.get("parameters", {})
    raw = data.get("raw_query", "").lower()
    
    try:
        if "motion" in raw or "kinematics" in raw or "vel" in raw or "accel" in raw:
            async for chunk in solve_kinematics(params):
                yield chunk
        elif "snell" in raw or "refraction" in raw or "optical" in raw:
            async for chunk in solve_optics(params):
                yield chunk
        elif "wave" in raw or "frequency" in raw or "lambda" in raw:
            async for chunk in solve_waves(params):
                yield chunk
        elif "doppler" in raw:
            async for chunk in solve_doppler(params):
                yield chunk
        else:
            yield {"type": "step", "content": "Applying General Physics Principles..."}
            yield {"type": "final", "answer": "Analysis complete. Please provide specific parameters for Light, Waves, or Atomic physics."}
    except Exception as e:
        yield {"type": "final", "answer": f"Physics Solver Error: {str(e)}"}

async def solve_optics(params):
    yield {"type": "step", "content": "Calculating Optical Refraction..."}
    n1 = float(params.get("n1", 1.0)) # Air
    theta1 = float(params.get("theta1", 30))
    n2 = float(params.get("n2", 1.5)) # Glass
    
    # Snell's Law: n1*sin(theta1) = n2*sin(theta2)
    sin_theta2 = (n1 * np.sin(np.radians(theta1))) / n2
    
    steps = ["### Optics Analysis (Snell's Law)"]
    if abs(sin_theta2) <= 1:
        theta2 = np.degrees(np.arcsin(sin_theta2))
        steps.append(f"- Medium 1 ($n_1$): {n1}")
        steps.append(f"- Incidence Angle ($\\theta_1$): {theta1}$^\\circ$")
        steps.append(f"- Medium 2 ($n_2$): {n2}")
        steps.append(f"**Refraction Angle ($\\theta_2$):** {theta2:.2f}$^\\circ$")
    else:
        steps.append("Total Internal Reflection occurs.")
        
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_waves(params):
    yield {"type": "step", "content": "Analyzing Wave Characteristics..."}
    v = float(params.get("v", 343)) # Speed of sound default
    f = float(params.get("f", 440)) # Frequency
    lam = float(params.get("lambda", params.get("wavelength", 0)))
    
    steps = ["### Wave Mechanics"]
    if f and v:
        lam_calc = v / f
        steps.append(f"- Wavelength ($\\lambda = v/f$): {lam_calc:.4f} m")
    elif lam and v:
        f_calc = v / lam
        steps.append(f"- Frequency ($f = v/\\lambda$): {f_calc:.2f} Hz")
    else:
        steps.append("Please provide speed and either frequency or wavelength.")
        
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_doppler(params):
    yield {"type": "step", "content": "Executing Doppler Effect Analysis..."}
    fs = float(params.get("fs", 440)) # Source frequency
    v = float(params.get("v", 343))  # Speed of sound
    vs = float(params.get("vs", 0))   # Source velocity (positive if moving away)
    vo = float(params.get("vo", 0))   # Observer velocity (positive if moving towards)
    
    f_obs = fs * ((v + vo) / (v + vs))
    
    steps = [
        "### Doppler Effect Report",
        f"- Source Frequency ($f_s$): {fs} Hz",
        f"- Medium Speed ($v$): {v} m/s",
        f"**Observed Frequency ($f_o$):** {f_obs:.2f} Hz"
    ]
    yield {"type": "final", "answer": "\n".join(steps)}

async def solve_kinematics(params):
    yield {"type": "step", "content": "Applying Kinematic Equations (SUVAT)..."}
    # v = u + at, s = ut + 0.5at^2, v^2 = u^2 + 2as
    u = float(params.get("u", params.get("vi", 0))) # initial velocity
    v = float(params.get("v", params.get("vf", 0))) # final velocity
    a = float(params.get("a", 0))                   # acceleration
    t = float(params.get("t", 0))                   # time
    s = float(params.get("s", params.get("d", 0)))  # displacement
    
    steps = ["### Kinematics: 1D Motion Analysis"]
    
    # Simple logic to find the missing variable if enough are present
    if u and a and t and not s:
        s_calc = u*t + 0.5*a*t**2
        steps.append(f"- Calculated Displacement ($s = ut + \\frac{1}{2}at^2$): {s_calc:.2f} m")
    elif u and v and t and not s:
        s_calc = (u+v)/2 * t
        steps.append(f"- Calculated Displacement ($s = \\frac{u+v}{2}t$): {s_calc:.2f} m")
    elif u and a and s and not v:
        v_calc = np.sqrt(u**2 + 2*a*s)
        steps.append(f"- Calculated Final Velocity ($v = \\sqrt{u^2 + 2as}$): {v_calc:.2f} m/s")
    elif v and a and t and not u:
        u_calc = v - a*t
        steps.append(f"- Calculated Initial Velocity ($u = v - at$): {u_calc:.2f} m/s")
    else:
        steps.append(f"**State:** $u={u}$m/s, $v={v}$m/s, $a={a}$m/s$^2$, $t={t}$s, $s={s}$m")
        steps.append("Provide 3 parameters to solve for the remaining kinematic variables.")
    
    yield {"type": "final", "answer": "\n".join(steps)}
