"""
Statistical Analysis Solver
Handles: descriptive stats, confidence intervals, normality tests,
         correlation, linear regression, hypothesis tests (t-test, chi-square).
"""

import asyncio
import re
import numpy as np
from scipy import stats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_data(params, raw_query):
    """
    Extract a numeric list from params['data'] or from raw text.
    Returns a numpy array (may be empty).
    """
    data_raw = params.get("data", [])

    if isinstance(data_raw, str):
        data_raw = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", data_raw)

    if data_raw:
        try:
            return np.array([float(x) for x in data_raw])
        except (TypeError, ValueError):
            pass

    # Fall back to raw_query numbers
    matches = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", raw_query or "")
    return np.array([float(x) for x in matches])


def _series_points(x_values, y_values):
    return [{"x": float(x), "y": float(y)} for x, y in zip(x_values, y_values)]


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

async def solve_statistics(data):
    yield {"type": "step", "content": "Initializing Statistical Analysis Engine..."}

    params    = data.get("parameters", {})
    raw       = data.get("raw_query",  "").lower()
    prob_type = data.get("problem_type", "").lower()

    arr = _parse_data(params, raw)

    if arr.size == 0:
        yield {"type": "final",
               "answer": ("The data list is empty or could not be parsed. "
                          "Please provide a list of numbers, e.g. `data: [1, 2, 3, 4, 5]`.")}
        return

    yield {"type": "step",
           "content": f"Processing {len(arr)} data points..."}

    try:
        if any(kw in raw or kw in prob_type
               for kw in ("regression", "correlation", "linear fit")):
            async for chunk in solve_regression(params, arr, raw):
                yield chunk

        elif any(kw in raw or kw in prob_type
                 for kw in ("t-test", "ttest", "hypothesis", "mean test")):
            async for chunk in solve_hypothesis_test(params, arr, raw):
                yield chunk

        elif any(kw in raw or kw in prob_type
                 for kw in ("chi", "goodness", "contingency")):
            async for chunk in solve_chi_square(params, arr, raw):
                yield chunk

        else:
            async for chunk in solve_descriptive(arr):
                yield chunk

    except Exception as exc:
        yield {"type": "final", "answer": f"Statistics Solver Error: {exc}"}


# ---------------------------------------------------------------------------
# Sub-solvers
# ---------------------------------------------------------------------------

async def solve_descriptive(arr):
    """Full descriptive statistics for a 1-D sample."""
    n        = len(arr)
    mean     = float(np.mean(arr))
    median   = float(np.median(arr))
    mode_res = stats.mode(arr, keepdims=True)
    mode_val = float(mode_res.mode[0])
    mode_cnt = int(mode_res.count[0])

    std  = float(np.std(arr, ddof=1))  if n > 1 else 0.0
    var  = float(np.var(arr, ddof=1))  if n > 1 else 0.0
    sem  = float(stats.sem(arr))       if n > 1 else 0.0
    skew = float(stats.skew(arr))      if n > 2 else float("nan")
    kurt = float(stats.kurtosis(arr))  if n > 3 else float("nan")

    q1, q3   = float(np.percentile(arr, 25)), float(np.percentile(arr, 75))
    iqr_val  = q3 - q1

    steps = [
        "### Descriptive Statistics",
        f"- **Sample size ($n$):** {n}",
        "",
        "#### Central Tendency",
        f"- **Mean ($\\bar{{x}}$):** {mean:.6g}",
        f"- **Median:** {median:.6g}",
        f"- **Mode:** {mode_val:.6g}  (appears {mode_cnt}×)",
        "",
        "#### Spread",
        f"- **Std deviation ($s$):** {std:.6g}",
        f"- **Variance ($s^2$):** {var:.6g}",
        f"- **Std error of mean (SEM):** {sem:.6g}",
        f"- **Range:** [{float(np.min(arr)):.6g}, {float(np.max(arr)):.6g}]",
        f"- **IQR (Q1–Q3):** {q1:.6g} – {q3:.6g}  (IQR = {iqr_val:.6g})",
        "",
        "#### Shape",
        f"- **Skewness:** {skew:.4f}",
        f"- **Excess kurtosis:** {kurt:.4f}",
    ]

    if n > 1:
        ci = stats.t.interval(0.95, df=n - 1, loc=mean, scale=sem)
        steps += [
            "",
            "#### Inference",
            f"- **95% CI for mean:** [{ci[0]:.6g}, {ci[1]:.6g}]",
        ]

    if n >= 8:
        # Shapiro-Wilk normality test (reliable for n ≤ 5000)
        stat_sw, p_sw = stats.shapiro(arr)
        conclusion    = "normal" if p_sw > 0.05 else "non-normal"
        steps += [
            "",
            "#### Normality (Shapiro–Wilk)",
            f"- $W = {stat_sw:.4f}$, $p = {p_sw:.4f}$",
            f"- Data appears **{conclusion}** at the 5% significance level.",
        ]

    # Histogram data for the diagram
    counts, bin_edges = np.histogram(arr, bins="auto")
    bin_centres       = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    yield {"type": "diagram",
           "diagram_type": "histogram",
           "data": _series_points(bin_centres, counts)}

    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_regression(params, arr, raw_query):
    """Simple / multiple linear regression.  Expects x and y in params or arr."""
    x_raw = params.get("x", params.get("x_data", []))
    y_raw = params.get("y", params.get("y_data", []))

    try:
        x_arr = np.array([float(v) for v in x_raw])
        y_arr = np.array([float(v) for v in y_raw])
    except (TypeError, ValueError):
        x_arr = np.array([])
        y_arr = np.array([])

    # If only one array was provided, try to split it evenly
    if x_arr.size == 0 and arr.size >= 4 and arr.size % 2 == 0:
        half  = arr.size // 2
        x_arr = arr[:half]
        y_arr = arr[half:]

    if x_arr.size < 2 or y_arr.size < 2 or x_arr.size != y_arr.size:
        yield {"type": "final",
               "answer": ("Linear regression requires equal-length x and y arrays "
                          "(at least 2 points each). "
                          "Pass `x: [...]` and `y: [...]` in parameters.")}
        return

    n        = len(x_arr)
    slope, intercept, r, p_val, se = stats.linregress(x_arr, y_arr)
    r2       = r ** 2
    y_pred   = slope * x_arr + intercept
    residuals = y_arr - y_pred
    rmse     = float(np.sqrt(np.mean(residuals ** 2)))

    yield {"type": "diagram",
           "diagram_type": "scatter_regression",
           "data": {
               "x":     x_arr.tolist(),
               "y":     y_arr.tolist(),
               "y_fit": y_pred.tolist(),
           }}

    steps = [
        "### Linear Regression",
        f"- **n:** {n} data points",
        f"- **Equation:** $\\hat{{y}} = {slope:.6g}x + ({intercept:.6g})$",
        f"- **Slope ($\\hat{{\\beta_1}}$):** {slope:.6g}  (SE = {se:.6g})",
        f"- **Intercept ($\\hat{{\\beta_0}}$):** {intercept:.6g}",
        "",
        "#### Goodness of Fit",
        f"- **$R$  (Pearson correlation):** {r:.6f}",
        f"- **$R^2$ (coefficient of determination):** {r2:.6f}",
        f"- **RMSE:** {rmse:.6g}",
        f"- **$p$-value (slope ≠ 0):** {p_val:.4g}",
        (f"  → Slope is **statistically significant** at 5% level."
         if p_val < 0.05 else
         f"  → Slope is **not** statistically significant at 5% level (p = {p_val:.4g})."),
    ]
    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_hypothesis_test(params, arr, raw_query):
    """One-sample or two-sample t-test."""
    mu0     = float(params.get("mu0", params.get("mu", 0)))
    alpha   = float(params.get("alpha", 0.05))
    two_arr = params.get("data2", [])

    if two_arr:
        # Two-sample t-test
        try:
            arr2 = np.array([float(v) for v in two_arr])
        except (TypeError, ValueError):
            arr2 = np.array([])

        if arr2.size < 2:
            yield {"type": "final",
                   "answer": "Two-sample test requires a second data array `data2`."}
            return

        t_stat, p_val = stats.ttest_ind(arr, arr2, equal_var=False)  # Welch
        n1, n2 = len(arr), len(arr2)
        steps = [
            "### Two-Sample Welch t-Test",
            f"- Group 1: n={n1}, mean={np.mean(arr):.6g}, s={np.std(arr, ddof=1):.6g}",
            f"- Group 2: n={n2}, mean={np.mean(arr2):.6g}, s={np.std(arr2, ddof=1):.6g}",
            f"- **t-statistic:** {t_stat:.4f}",
            f"- **p-value (two-tailed):** {p_val:.6f}",
            f"- **Decision (α = {alpha}):** "
            + ("Reject $H_0$ — means differ significantly."
               if p_val < alpha else
               "Fail to reject $H_0$ — no significant difference."),
        ]

    else:
        # One-sample t-test
        n       = len(arr)
        mean    = float(np.mean(arr))
        std     = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        sem     = float(stats.sem(arr))       if n > 1 else 0.0
        t_stat, p_val = stats.ttest_1samp(arr, mu0)
        ci      = stats.t.interval(1 - alpha, df=n - 1, loc=mean, scale=sem)

        steps = [
            "### One-Sample t-Test",
            f"- **Null hypothesis ($H_0$):** $\\mu = {mu0}$",
            f"- **Sample:** n={n}, $\\bar{{x}}={mean:.6g}$, $s={std:.6g}$",
            f"- **t-statistic:** {t_stat:.4f}",
            f"- **p-value (two-tailed):** {p_val:.6f}",
            f"- **{int((1-alpha)*100)}% CI:** [{ci[0]:.6g}, {ci[1]:.6g}]",
            f"- **Decision (α = {alpha}):** "
            + ("Reject $H_0$ — sample mean differs significantly from μ₀."
               if p_val < alpha else
               "Fail to reject $H_0$ — insufficient evidence against μ₀."),
        ]

    yield {"type": "final", "answer": "\n".join(steps)}


async def solve_chi_square(params, arr, raw_query):
    """Chi-square goodness-of-fit test."""
    expected_raw = params.get("expected", [])

    try:
        expected = np.array([float(v) for v in expected_raw])
    except (TypeError, ValueError):
        expected = np.array([])

    if expected.size == 0:
        # Uniform expectation
        expected = np.full_like(arr, fill_value=float(np.mean(arr)))

    if arr.size != expected.size:
        yield {"type": "final",
               "answer": ("Chi-square test requires observed and expected arrays "
                          "of the same length. Pass `expected: [...]` in parameters.")}
        return

    chi2, p_val = stats.chisquare(f_obs=arr, f_exp=expected)
    df          = arr.size - 1

    steps = [
        "### Chi-Square Goodness-of-Fit Test",
        f"- **Observed:** {arr.tolist()}",
        f"- **Expected:** {expected.tolist()}",
        f"- **χ² statistic:** {chi2:.4f}",
        f"- **Degrees of freedom:** {df}",
        f"- **p-value:** {p_val:.6f}",
        f"- **Decision (α = 0.05):** "
        + ("Reject $H_0$ — observed differs significantly from expected."
           if p_val < 0.05 else
           "Fail to reject $H_0$ — no significant departure from expected."),
    ]
    yield {"type": "final", "answer": "\n".join(steps)}
