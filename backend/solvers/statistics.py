import asyncio
import numpy as np
from scipy import stats

async def solve_statistics(data):
    yield {"type": "step", "content": "Initializing Statistical Analysis Engine..."}
    
    params = data.get("parameters", {})
    raw = data.get("raw_query", "").lower()
    
    # Try to extract data points
    data_points = params.get("data", [])
    if not data_points:
        # Try to parse from string if it looks like [1,2,3]
        import re
        matches = re.findall(r"[-+]?\d*\.\d+|\d+", raw)
        data_points = [float(x) for x in matches]
        
    if not data_points:
        yield {"type": "final", "answer": "Please provide a list of data points for statistical analysis."}
        return

    arr = np.array(data_points)
    
    yield {"type": "step", "content": f"Processing {len(arr)} data points..."}
    
    mean = np.mean(arr)
    median = np.median(arr)
    std = np.std(arr, ddof=1) if len(arr) > 1 else 0
    var = np.var(arr, ddof=1) if len(arr) > 1 else 0
    
    steps = [
        "### Statistical Summary",
        f"- **Sample Size ($n$):** {len(arr)}",
        f"- **Mean ($\\mu$):** {mean:.4f}",
        f"- **Median:** {median:.4f}",
        f"- **Std Deviation ($s$):** {std:.4f}",
        f"- **Variance ($s^2$):** {var:.4f}",
        f"- **Range:** {np.min(arr)} to {np.max(arr)}"
    ]
    
    if len(arr) > 1:
        # Confidence Interval (95%)
        sem = stats.sem(arr)
        ci = stats.t.interval(0.95, len(arr)-1, loc=mean, scale=sem)
        steps.append(f"- **95% Conf. Interval:** [{ci[0]:.4f}, {ci[1]:.4f}]")

    yield {"type": "final", "answer": "\n".join(steps)}
