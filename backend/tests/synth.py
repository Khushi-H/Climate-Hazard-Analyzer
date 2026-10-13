"""Synthetic but deliberately messy daily Tmax series for tests."""
import numpy as np
import pandas as pd


def make_series(start_year=1990, end_year=2020, seed=0, warming=0.04, messy=True):
    idx = pd.date_range(f"{start_year}-01-01", f"{end_year}-12-31", freq="D")
    doy = idx.dayofyear.to_numpy()
    rng = np.random.default_rng(seed)
    base = 30 + 8 * np.sin(2 * np.pi * (doy - 105) / 365.25)
    vals = base + warming * (idx.year.to_numpy() - start_year) + rng.normal(0, 1.8, len(idx))
    # inject heatwaves that become more frequent over time (hot season)
    for y in range(start_year, end_year + 1):
        n = 1 + (y - start_year) // 5
        for _ in range(n):
            st = pd.Timestamp(f"{y}-04-01") + pd.Timedelta(days=int(rng.integers(0, 70)))
            ln = int(rng.integers(4, 8))
            m = (idx >= st) & (idx < st + pd.Timedelta(days=ln))
            vals[m] += 8
    out = [float(round(v, 2)) for v in vals]
    if messy:
        out[400] = 99.9    # impossible value
        out[800] = -80.0   # impossible value
        out[1200] = out[1199] + 30.0  # isolated spike
        for i in (2000, 2001):          # short gap -> interpolated
            out[i] = None
        for i in range(3000, 3012):     # long gap -> left missing
            out[i] = None
    return [d.strftime("%Y-%m-%d") for d in idx], out
