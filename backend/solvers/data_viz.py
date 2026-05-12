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
from solvers.utils import clean_math_string

async def solve_function_plot(sub):
    yield {"type": "step", "content": "Generating function plot..."}
    params = sub.get("parameters", {})
    expr_str = params.get("expression", "")
    expr_str = clean_math_string(expr_str)
    bounds = params.get("bounds", {})
    
    # Default bounds if not provided
    x_min, x_max = -10, 10
    var_name = "x"
    
    if bounds:
        for v, b in bounds.items():
            var_name = v
            x_min, x_max = b[0], b[1]
            break
            
    try:
        # Check if it's "y = ..."
        if "=" in expr_str:
            expr_str = expr_str.split("=", 1)[1].strip()
            
        x_sym = sp.Symbol(var_name)
        func_expr = sp.sympify(expr_str)
        f_lambdified = sp.lambdify(x_sym, func_expr, "numpy")
        
        x_vals = np.linspace(x_min, x_max, 500)
        y_vals = f_lambdified(x_vals)
        
        plt.figure(figsize=(10, 6))
        plt.plot(x_vals, y_vals, color='#3b82f6', linewidth=2)
        plt.axhline(0, color='white', linewidth=0.5, alpha=0.3)
        plt.axvline(0, color='white', linewidth=0.5, alpha=0.3)
        plt.grid(True, linestyle='--', alpha=0.2)
        plt.title(f"Plot of $f({var_name}) = {sp.latex(func_expr)}$")
        plt.xlabel(var_name)
        plt.ylabel(f"f({var_name})")
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
                "caption": f"Visualization of {expr_str} over [{x_min}, {x_max}]."
            }
        }
        yield {"type": "final", "answer": f"Function $f({var_name})$ has been successfully plotted."}
        
    except Exception as e:
        yield {"type": "final", "answer": f"Error plotting function: {str(e)}"}

async def solve_data_viz(sub: dict):
    yield {"type": "step", "content": "Initializing Advanced Data Visualization Kernel..."}
    
    params = sub.get("parameters", {})
    table_data = params.get("table_data", "")
    plot_config = params.get("plot_config", {})
    expr = params.get("expression", "")
    
    if not table_data and expr:
        async for chunk in solve_function_plot(sub):
            yield chunk
        return

    if not table_data:
        yield {"type": "final", "answer": "Error: No table data found to visualize. Please upload a CSV/XLSX file or provide text-based table data."}
        return

    try:
        # Parsing data
        try:
            decoded = base64.b64decode(table_data).decode('utf-8')
            df = pd.read_csv(io.StringIO(decoded))
        except:
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
        else:
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

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
            
        yield {"type": "final", "answer": answer}
        
    except Exception as e:
        yield {"type": "final", "answer": f"Data Viz kernel error: {str(e)}"}
