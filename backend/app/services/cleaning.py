"""Turning noisy real-world daily series into something safe to analyse.

Steps (all counted and reported back to the user as data-quality info):
  1. de-duplicate and re-index to a complete daily calendar (exposes silently missing dates)
  2. physical-range check (-70..60 deg C) -> implausible values removed
  3. spike check: a single day far from its own 15-day rolling median AND from both neighbours -> removed
     (real heatwave days have hot neighbours, so they are never treated as spikes)
  4. short gaps (<= 3 days) linearly interpolated; longer gaps stay missing and are never bridged
"""
from typing import Optional, Tuple

import numpy as np
import pandas as pd

PHYS_MIN, PHYS_MAX = -70.0, 60.0
MAX_INTERP_GAP = 3
SPIKE_FLOOR_C = 12.0


def clean_series(dates, values) -> Tuple[pd.DatetimeIndex, np.ndarray, dict]:
    idx = pd.to_datetime(pd.Index(dates))
    s = pd.Series([np.nan if v is None else float(v) for v in values], index=idx, dtype=float)
    s = s[~s.index.duplicated(keep="first")].sort_index()
    full = pd.date_range(s.index.min(), s.index.max(), freq="D")
    missing_dates = len(full) - len(s)
    s = s.reindex(full)
    s = s.replace([np.inf, -np.inf], np.nan)
    total_days = len(s)
    missing_raw = int(s.isna().sum())

    oob = (s < PHYS_MIN) | (s > PHYS_MAX)
    n_oob = int(oob.sum())
    s[oob] = np.nan

    med = s.rolling(15, center=True, min_periods=5).median()
    resid = s - med
    mad = float(np.nanmedian(np.abs(resid - np.nanmedian(resid)))) if resid.notna().any() else 0.0
    limit = max(SPIKE_FLOOR_C, 6 * 1.4826 * mad)
    # Only an ISOLATED jump is a sensor-style spike. A genuinely hot day sits next to other hot days,
    # so it is kept: removing real heatwave peaks would bias the very thing we measure.
    jump_prev = (s - s.shift(1)).abs() > limit / 2
    jump_next = (s - s.shift(-1)).abs() > limit / 2
    spikes = (resid.abs() > limit) & jump_prev.fillna(True) & jump_next.fillna(True)
    n_spikes = int(spikes.sum())
    s[spikes] = np.nan

    isna = s.isna()
    run_id = (isna != isna.shift()).cumsum()
    run_len = isna.groupby(run_id).transform("sum")
    short = isna & (run_len <= MAX_INTERP_GAP)
    interp = s.interpolate(method="time", limit_area="inside")
    fill_mask = short & interp.notna()
    s[fill_mask] = interp[fill_mask]
    n_interp = int(fill_mask.sum())

    remaining = int(s.isna().sum())
    quality = {
        "total_days": total_days,
        "missing_dates": int(missing_dates),
        "missing_raw": missing_raw,
        "out_of_range_removed": n_oob,
        "spikes_removed": n_spikes,
        "interpolated": n_interp,
        "remaining_missing": remaining,
        "completeness_pct": round(100.0 * (total_days - remaining) / total_days, 2) if total_days else 0.0,
    }
    return s.index, s.to_numpy(dtype=float), quality