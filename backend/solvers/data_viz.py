import asyncio
import pandas as pd
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import r2_score
import sympy as sp
import re
from solvers.utils import clean_math_string, safe_sympify, simplify_math, detect_variables


def _coerce_plot_values(values, x_vals):
    if np.isscalar(values):
        return np.full_like(x_vals, float(values), dtype=float)
    array = np.asarray(values, dtype=float)
    if array.shape == ():
        return np.full_like(x_vals, float(array), dtype=float)
    return array


def _extract_inline_series(raw_query):
    text = clean_math_string(raw_query)
    if not text:
        return None

    number_pattern = r"[-+]?\d*\.?\d+"
    values_match = re.search(r"values?\s*(?:\(.*?\))?\s*:\s*([0-9.,\s-]+)", text, re.IGNORECASE)
    if values_match:
        values = [float(item) for item in re.findall(number_pattern, values_match.group(1))]
        if len(values) >= 2:
            interval_match = re.search(r"(\d+(?:\.\d+)?)\s*[- ]?meter intervals?", text, re.IGNORECASE)
            interval = float(interval_match.group(1)) if interval_match else 1.0
            start_match = re.search(r"from\s+(-?\d+(?:\.\d+)?)\s+to\s+(-?\d+(?:\.\d+)?)", text, re.IGNORECASE)
            if start_match:
                start = float(start_match.group(1))
            else:
                start = 0.0
            x_values = [start + idx * interval for idx in range(len(values))]
            return {
                "columns": ["x", "y"],
                "rows": [{"x": x, "y": y} for x, y in zip(x_values, values)],
                "title": "Extracted data from prompt",
            }

    return None

async def solve_function_plot(sub):
    yield {"type": "step", "content": "Initializing Advanced Data Visualization Kernel..."}
    params = sub.get("parameters", {})
    expr_str = params.get("expression", "")

    # Normalize assignment-like inputs from word problems/logging:
    # Examples:
    #   "f = sin(x)"   -> "sin(x)"
    #   "y=cos(x)"     -> "cos(x)"
    #   "y = f(x)+1"   -> "f(x)+1"
    # Only strip when the LHS looks like a simple variable/name (not a multi-variable equation).
    expr_str = (expr_str or "").strip()
    assignment_match = re.match(r"^\s*([A-Za-z_]\w*)\s*=\s*(.+)$", expr_str)
    if assignment_match:
        lhs, rhs = assignment_match.group(1), assignment_match.group(2).strip()
        # If rhs still contains other assignment-like "=", keep original (likely a real equation).
        if "=" not in rhs:
            expr_str = rhs

    # Handle common trigonometric names
    trig_replacements = {
        r"\bsine\b": "sin",
        r"\bcosine\b": "cos",
        r"\btangent\b": "tan",
        r"\bsecant\b": "sec",
        r"\bcosecant\b": "csc",
        r"\bcotangent\b": "cot"
    }
    for pattern, repl in trig_replacements.items():
        expr_str = re.sub(pattern, repl, expr_str, flags=re.IGNORECASE)
    
    expr_str = clean_math_string(expr_str)
    
    yield {"type": "step", "content": f"Normalized expression: $f = {expr_str}$"}
    
    bounds = params.get("bounds", {})
    # Default bounds if not provided
    x_min = float(params.get("x_min", -10))
    x_max = float(params.get("x_max", 10))
    var_name = "x"
    
    if bounds:
        for v, b in bounds.items():
            var_name = v
            x_min, x_max = b[0], b[1]
            break
            
    yield {"type": "step", "content": f"Computing values over domain [{x_min}, {x_max}]..."}
    
    try:
        # Detect multiple equations if passed as one string
        sub_exprs = [expr_str]
        for delim in [" and ", ";", "\n", ", "]:
            if delim in expr_str.lower():
                sub_exprs = [e.strip() for e in re.split(delim, expr_str, flags=re.IGNORECASE) if e.strip()]
                break
        
        # Pick the best equation to plot (one with an equals sign and variables)
        plot_eq = sub_exprs[0]
        for e in sub_exprs:
            if "=" in e and any(c.isalpha() for c in e):
                plot_eq = e
                break

        x_sym = sp.Symbol(var_name)
        symbol_names = sorted(set(re.findall(r"[A-Za-z_]\w*", plot_eq or "")) | {var_name})
        symbol_map = {name: sp.Symbol(name) for name in symbol_names}

        if "=" in plot_eq:
            yield {"type": "step", "content": "Parsing equation and isolating dependent variable..."}
            lhs_text, rhs_text = [part.strip() for part in plot_eq.split("=", 1)]
            lhs = safe_sympify(lhs_text, symbols=symbol_map)
            rhs = safe_sympify(rhs_text, symbols=symbol_map)
            equation = sp.Eq(lhs, rhs)
            free_symbols = sorted(equation.free_symbols, key=lambda sym: sym.name)

            dependent_var = None
            # Prioritize y as dependent variable
            if sp.Symbol("y") in free_symbols:
                dependent_var = sp.Symbol("y")
            elif len(free_symbols) >= 2:
                # Pick the first non-x symbol
                dependent_var = next((sym for sym in free_symbols if sym != x_sym), None)
            
            if dependent_var is not None:
                solutions = sp.solve(equation, dependent_var)
                if not solutions:
                    # Try solving for x if y failed
                    solutions = sp.solve(equation, x_sym)
                    if solutions:
                        func_expr = solutions[0]
                        ylabel = x_sym.name
                        x_sym = dependent_var
                        var_name = dependent_var.name
                    else:
                        raise ValueError("Could not isolate any variable for plotting.")
                else:
                    func_expr = solutions[0]
                    ylabel = dependent_var.name
                
                caption_expr = f"{ylabel} = {sp.sstr(func_expr)}"
            else:
                func_expr = lhs - rhs
                ylabel = "f(x)"
                caption_expr = plot_eq
        else:
            func_expr = safe_sympify(plot_eq, symbols=symbol_map)
            ylabel = f"f({var_name})"
            caption_expr = plot_eq

        # Simplify the function before plotting
        yield {"type": "step", "content": "Simplifying expression for optimal performance..."}
        func_expr = simplify_math(func_expr)
        
        # Ensure func_expr only contains the independent variable
        # But wait, what if it's 3D?
        free_symbols = [s for s in func_expr.free_symbols]
        independent_vars = [s for s in free_symbols if s.name in [var_name, "x", "y", "t"]]
        
        if len(independent_vars) >= 2:
            # 3D Plot logic
            yield {"type": "step", "content": "Multivariable expression detected. Generating 3D topographic surface..."}
            v1, v2 = independent_vars[0], independent_vars[1]
            f_3d = sp.lambdify((v1, v2), func_expr, "numpy")
            
            # Use higher density for smoother surface
            x_mesh = np.linspace(x_min, x_max, 60)
            y_mesh = np.linspace(x_min, x_max, 60)
            X, Y = np.meshgrid(x_mesh, y_mesh)
            
            try:
                Z = f_3d(X, Y)
                if np.isscalar(Z):
                    Z = np.full_like(X, float(Z))
                
                # Filter out exploding values (singularities)
                Z = np.clip(Z, -1e6, 1e6)
                
                from mpl_toolkits.mplot3d import Axes3D
                fig = plt.figure(figsize=(10, 8), dpi=100)
                ax = fig.add_subplot(111, projection='3d')
                
                # Engineering-style surface
                surf = ax.plot_surface(X, Y, Z, cmap='plasma', edgecolor='none', alpha=0.9, 
                                     antialiased=True, rcount=100, ccount=100)
                
                # Add contours on the bottom plane
                offset = np.min(Z) if not np.isnan(np.min(Z)) else -10
                ax.contour(X, Y, Z, zdir='z', offset=offset, cmap='plasma', alpha=0.5)
                
                fig.colorbar(surf, ax=ax, shrink=0.5, aspect=10, pad=0.1)
                
                ax.set_title(f"3D Analysis: $z = {sp.latex(func_expr)}$", pad=20)
                ax.set_xlabel(v1.name, labelpad=10)
                ax.set_ylabel(v2.name, labelpad=10)
                ax.set_zlabel("Result ($z$)", labelpad=10)
                
                # Set viewing angle for better perspective
                ax.view_init(elev=25, azim=45)
                
                plt.style.use('dark_background')
                plt.tight_layout()
            except Exception as e3d:
                raise ValueError(f"3D computation error: {str(e3d)}")
        else:
            # 2D Plot
            f_lambdified = sp.lambdify(x_sym, func_expr, "numpy")
            
            x_vals = np.linspace(x_min, x_max, 500)
            y_vals = _coerce_plot_values(f_lambdified(x_vals), x_vals)
            
            plt.figure(figsize=(10, 6))
            plt.plot(x_vals, y_vals, color=params.get("color", '#3b82f6'), 
                     linestyle=params.get("linestyle", '-'), linewidth=2)
            plt.axhline(0, color='white', linewidth=0.5, alpha=0.3)
            plt.axvline(0, color='white', linewidth=0.5, alpha=0.3)
            plt.grid(True, linestyle='--', alpha=0.2)
            plt.title(params.get("title") or f"Plot of ${sp.latex(func_expr)}$")
            plt.xlabel(params.get("xlabel") or var_name)
            plt.ylabel(params.get("ylabel") or ylabel)
            plt.style.use('dark_background')
        
        buf_png = io.BytesIO()
        plt.savefig(buf_png, format='png', transparent=True, dpi=150)
        buf_png.seek(0)
        png_b64 = base64.b64encode(buf_png.read()).decode('utf-8')
        plt.close()
        
        yield {
            "type": "diagram",
            "diagram_type": "plot",
            "data": {
                "image": f"data:image/png;base64,{png_b64}",
                "caption": f"Visualization of {caption_expr} over [{x_min}, {x_max}]."
            }
        }

        summary_lines = [
            "### Graph Ready",
            f"- Plotted over {var_name} in [{x_min}, {x_max}]",
            f"- Relation: ${sp.latex(func_expr)}$",
        ]
        if len(getattr(func_expr, "free_symbols", [])) <= 1:
            try:
                y_intercept = float(func_expr.subs(x_sym, 0))
                summary_lines.append(f"- y-intercept: {y_intercept:.4f}")
            except Exception:
                pass
            try:
                roots = sp.solve(sp.Eq(func_expr, 0), x_sym)
                real_roots = [root for root in roots if getattr(root, "is_real", False) or root.is_real is None]
                if real_roots:
                    root_text = ", ".join(sp.sstr(root) for root in real_roots[:4])
                    summary_lines.append(f"- x-intercept(s): {root_text}")
            except Exception:
                pass
        yield {"type": "final", "answer": "\n".join(summary_lines)}
        
    except Exception as e:
        yield {"type": "error", "message": f"Unable to plot this relation cleanly: {str(e)}"}

async def solve_data_viz(sub: dict):
    yield {"type": "step", "content": "Initializing Advanced Data Visualization Kernel..."}
    
    params = sub.get("parameters", {})
    table_data = params.get("table_data", "")
    plot_config = params.get("plot_config", {})
    expr = params.get("expression", "")
    raw_query = sub.get("raw_query", "")
    
    if not table_data and expr:
        async for chunk in solve_function_plot(sub):
            yield chunk
        return

    inline_series = None if table_data else _extract_inline_series(raw_query)
    if inline_series is not None:
        df = pd.DataFrame(inline_series["rows"])
        plot_config = {
            "type": plot_config.get("type", "line"),
            "title": plot_config.get("title") or "Deflection vs Position",
            "xlabel": plot_config.get("xlabel") or "Position (m)",
            "ylabel": plot_config.get("ylabel") or "Deflection (mm)",
            "x": "x",
            "y": "y",
            "annotate_max": True,
        }
    else:
        df = None

    if not table_data:
        if df is None:
            yield {"type": "final", "answer": "I could not find graphable data in the prompt. Provide an equation, upload a table, or include clear numeric values."}
            return

    try:
        # Parsing data
        if df is None:
            try:
                decoded = base64.b64decode(table_data).decode('utf-8')
                df = pd.read_csv(io.StringIO(decoded))
            except Exception:
                df = pd.read_csv(io.StringIO(table_data))
            
        yield {"type": "step", "content": f"Successfully parsed table with {len(df)} rows."}
        
        # Detect Stress-Strain
        cols_lower = [c.lower() for c in df.columns]
        is_stress_strain = "stress" in cols_lower and "strain" in cols_lower
        
        # Plotting
        yield {"type": "step", "content": f"Generating {'Stress-Strain' if is_stress_strain else 'Technical'} Plot..."}
        
        plt.figure(figsize=(10, 6))
        
        plot_type = plot_config.get("type", "line").lower()
        custom_title = plot_config.get("title")
        custom_xlabel = plot_config.get("xlabel")
        custom_ylabel = plot_config.get("ylabel")
        
        plot_results = {}
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        if is_stress_strain:
            strain_col = [c for c in df.columns if c.lower() == "strain"][0]
            stress_col = [c for c in df.columns if c.lower() == "stress"][0]
            x, y = df[strain_col], df[stress_col]
            plt.plot(x, y, 'o-', label="Experimental Data", color='#ffffff', alpha=0.5, markersize=3)
            
            elastic_limit = int(len(x) * 0.15) if len(x) > 10 else len(x)
            z = np.polyfit(x[:elastic_limit], y[:elastic_limit], 1)
            p = np.poly1d(z)
            plt.plot(x, p(x), '--', label=f"Elastic Modulus (E ≈ {z[0]/1e9:.1f} GPa)", color='#3b82f6')
            
            plt.xlabel(custom_xlabel or "Strain (ε)")
            plt.ylabel(custom_ylabel or "Stress (σ) [Pa]")
            plt.title(custom_title or "Stress-Strain Curve Analysis")
            plot_results['modulus'] = z[0]
        
        if len(numeric_cols) >= 2:
            x_col = plot_config.get("x") or numeric_cols[0]
            y_col = plot_config.get("y") or numeric_cols[1]
            x, y = df[x_col].values, df[y_col].values
            
            if plot_type == "scatter":
                plt.scatter(x, y, label="Data Points", color='#ffffff', alpha=0.6, s=30)
            elif plot_type == "bar":
                plt.bar(x, y, color='#3b82f6', alpha=0.7, label=y_col)
            else: # line
                plt.plot(x, y, 'o-', color='#ffffff', alpha=0.8, linewidth=1, markersize=4, label=y_col)
            
            # Regression (Only for scatter/line)
            if plot_type != "bar":
                z = np.polyfit(x, y, 1)
                p = np.poly1d(z)
                y_pred = p(x)
                r2 = r2_score(y, y_pred)
                plt.plot(x, y_pred, '--', label=f"Fit: R²={r2:.3f}", color='#ef4444')
                plot_results['r2'] = r2
                plot_results['equation'] = f"y = {z[0]:.2f}x + {z[1]:.2f}"

            if plot_config.get("annotate_max"):
                max_idx = int(np.argmax(y))
                plt.scatter([x[max_idx]], [y[max_idx]], color='#ef4444', s=60, zorder=5)
                plt.annotate(
                    f"Max ({x[max_idx]:.2f}, {y[max_idx]:.2f})",
                    (x[max_idx], y[max_idx]),
                    textcoords="offset points",
                    xytext=(10, 10),
                    color='white',
                    fontsize=9,
                )
                plot_results['max_point'] = {"x": float(x[max_idx]), "y": float(y[max_idx])}
            
            plt.xlabel(custom_xlabel or x_col)
            plt.ylabel(custom_ylabel or y_col)
            plt.title(custom_title or f"{y_col} vs {x_col} Analysis")
        else:
            plt.close()
            yield {
                "type": "table",
                "title": "Uploaded dataset preview",
                "columns": list(df.columns),
                "rows": df.head(100).to_dict(orient="records"),
            }
            yield {
                "type": "final",
                "answer": "### Data Table Loaded\nA readable table preview is available below. Add at least two numeric columns to generate a graph automatically.",
            }
            return
            
        plt.grid(True, linestyle='--', alpha=0.2)
        plt.legend()
        plt.style.use('dark_background')
        
        # Exports
        buf_png = io.BytesIO()
        plt.savefig(buf_png, format='png', transparent=True, dpi=150)
        buf_png.seek(0)
        png_b64 = base64.b64encode(buf_png.read()).decode('utf-8')
        
        buf_svg = io.BytesIO()
        plt.savefig(buf_svg, format='svg', transparent=True)
        buf_svg.seek(0)
        svg_b64 = base64.b64encode(buf_svg.read()).decode('utf-8')
        plt.close()
        
        csv_data = df.to_csv(index=False)
        
        yield {
            "type": "diagram",
            "diagram_type": "plot",
            "data": {
                "image": f"data:image/png;base64,{png_b64}",
                "svg": f"data:image/svg+xml;base64,{svg_b64}",
                "csv": csv_data,
                "caption": "Interactive analysis completed.",
                "table_json": df.head(100).to_dict(orient='records'),
                "columns": list(df.columns)
            }
        }
        yield {
            "type": "table",
            "title": "Dataset preview",
            "columns": list(df.columns),
            "rows": df.head(100).to_dict(orient="records"),
        }
        
        answer = "### Technical Data Report\n"
        if is_stress_strain:
            answer += f"- **Estimated Elastic Modulus:** {plot_results['modulus']/1e9:.2f} GPa\n"
        elif 'r2' in plot_results:
            answer += f"- **Regression Equation:** {plot_results['equation']}\n"
            answer += f"- **R-squared ($R^2$):** {plot_results['r2']:.4f}\n"
        if 'max_point' in plot_results:
            answer += f"- **Maximum point:** ({plot_results['max_point']['x']:.2f}, {plot_results['max_point']['y']:.2f})\n"
            
        yield {"type": "final", "answer": answer}
        
    except Exception as e:
        yield {"type": "error", "message": f"Visualization failed: {str(e)}"}
