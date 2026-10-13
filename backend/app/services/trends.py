"""Trend statistics: OLS regression, Mann-Kendall test, Sen's slope, rolling mean, period change."""
import math

import numpy as np
import pandas as pd
from scipy import stats

METRICS = {
    "heatwave_days": {"label": "Heatwave days", "unit": "days/yr"},
    "events": {"label": "Heatwave events", "unit": "events/yr"},
    "max_duration": {"label": "Longest heatwave", "unit": "days"},
    "mean_intensity": {"label": "Mean intensity", "unit": "deg C above threshold"},
}
MIN_POINTS = 8


def mann_kendall(x, y, alpha: float = 0.05):
    """Mann-Kendall trend test (tie-corrected) with Sen's slope. Returns None if < 4 points."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 4:
        return None
    iu = np.triu_indices(n, 1)
    dy = (y[None, :] - y[:, None])[iu]
    dx = (x[None, :] - x[:, None])[iu]
    s = int(np.sign(dy).sum())
    _, counts = np.unique(y, return_counts=True)
    t = counts[counts > 1].astype(float)
    var = (n * (n - 1) * (2 * n + 5) - np.sum(t * (t - 1) * (2 * t + 5))) / 18.0
    if var <= 0 or s == 0:
        z = 0.0
    elif s > 0:
        z = (s - 1) / math.sqrt(var)
    else:
        z = (s + 1) / math.sqrt(var)
    p = float(2 * stats.norm.sf(abs(z)))
    tau = s / (n * (n - 1) / 2)
    sen = float(np.median(dy / dx))
    intercept = float(np.median(y - sen * x))
    significant = p < alpha
    trend = "no significant trend"
    if significant:
        trend = "increasing" if z > 0 else "decreasing"
    return {
        "trend": trend,
        "significant": bool(significant),
        "z": round(float(z), 3),
        "p_value": round(p, 4),
        "tau": round(float(tau), 3),
        "s": s,
        "sen_slope_per_year": sen,
        "sen_slope_per_decade": round(sen * 10, 3),
        "sen_intercept": intercept,
    }


def window_change(y):
    """Mean of the first k usable years vs the last k (k = 10, or a third of the record if shorter)."""
    n = len(y)
    k = max(3, min(10, n // 3))
    first = float(np.mean(y[:k]))
    last = float(np.mean(y[-k:]))
    pct = (last - first) / first * 100.0 if first > 0 else None
    return {
        "window_years": k,
        "first_mean": round(first, 3),
        "last_mean": round(last, 3),
        "abs_change": round(last - first, 3),
        "pct_change": None if pct is None else round(pct, 1),
        "small_base": bool(first < 1.0),
    }


def _bundle(years, values, usable, rolling_window: int = 5):
    pts = [(yr, v) for yr, v, u in zip(years, values, usable) if u and v is not None]
    series = [v if (u and v is not None) else None for v, u in zip(values, usable)]
    if len(pts) < MIN_POINTS:
        return {"available": False, "reason": f"Only {len(pts)} usable years; at least {MIN_POINTS} are needed for a trend.", "series": series}
    x = np.array([p[0] for p in pts], dtype=float)
    y = np.array([p[1] for p in pts], dtype=float)
    lin = stats.linregress(x, y)
    fit = [float(lin.slope * yr + lin.intercept) for yr in years]
    rolling = (
        pd.Series([np.nan if v is None else v for v in series], index=years, dtype=float)
        .rolling(rolling_window, center=True, min_periods=3)
        .mean()
        .to_numpy()
    )
    return {
        "available": True,
        "series": series,
        "rolling": rolling,
        "fit": fit,
        "linear": {
            "slope_per_year": float(lin.slope),
            "slope_per_decade": round(float(lin.slope) * 10, 3),
            "intercept": float(lin.intercept),
            "r2": round(float(lin.rvalue) ** 2, 3),
            "p_value": round(float(lin.pvalue), 4),
        },
        "mann_kendall": mann_kendall(x, y),
        "change": window_change(y),
        "n_years": len(pts),
    }


def build_trends(yearly: list) -> dict:
    years = [r["year"] for r in yearly]
    usable = [r["usable"] for r in yearly]
    out = {"years": years, "rolling_window": 5, "metrics": {}}
    for key, info in METRICS.items():
        b = _bundle(years, [r[key] for r in yearly], usable)
        b.update(label=info["label"], unit=info["unit"])
        out["metrics"][key] = b
    return out
