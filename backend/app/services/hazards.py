"""Heatwave detection.

Definition used:
  A heatwave is a run of >= `min_days` consecutive days whose maximum temperature exceeds the
  `percentile`-th percentile threshold for the region.

Two threshold methods:
  fixed    - one threshold: percentile of ALL daily Tmax in the selected period (the brief's definition)
  calendar - one threshold per day-of-year: percentile of Tmax in a +-7 day window around that day
             (standard seasonal definition; also flags warm spells outside the hot season)

Missing days are never counted as hot and always break a run (a gap is never assumed to be hot).
An event is attributed to the year it starts in.
"""
import calendar

import numpy as np
import pandas as pd

MIN_YEAR_COVERAGE = 0.8


class InsufficientDataError(ValueError):
    pass


def compute_threshold(index: pd.DatetimeIndex, values: np.ndarray, percentile: float, method: str, half_window: int = 7):
    valid = np.isfinite(values)
    if valid.sum() < 365 * 5:
        raise InsufficientDataError("Not enough valid daily data (need at least 5 years) to compute a percentile threshold.")
    if method == "fixed":
        t = float(np.nanpercentile(values, percentile))
        return np.full(len(values), t), {"method": "fixed", "percentile": percentile, "value": round(t, 2), "min": round(t, 2), "max": round(t, 2)}

    doy = index.dayofyear.to_numpy()
    per_doy = np.full(367, np.nan)
    offs = np.arange(-half_window, half_window + 1)
    for d in range(1, 367):
        window_days = ((d - 1 + offs) % 366) + 1
        mask = np.isin(doy, window_days) & valid
        if mask.sum() >= 30:
            per_doy[d] = np.percentile(values[mask], percentile)
    if np.isnan(per_doy[1:]).all():
        raise InsufficientDataError("Not enough data to compute seasonal thresholds.")
    fill = float(np.nanmean(per_doy[1:]))
    per_doy = np.where(np.isnan(per_doy), fill, per_doy)
    thr = per_doy[doy]
    body = per_doy[1:]
    return thr, {
        "method": "calendar",
        "percentile": percentile,
        "value": round(float(body.mean()), 2),
        "min": round(float(body.min()), 2),
        "max": round(float(body.max()), 2),
    }


def detect_events(index: pd.DatetimeIndex, values: np.ndarray, thr: np.ndarray, min_days: int) -> list:
    above = np.isfinite(values) & (values > thr)
    if not above.any():
        return []
    padded = np.concatenate(([0], above.astype(np.int8), [0]))
    diff = np.diff(padded)
    starts = np.where(diff == 1)[0]
    ends = np.where(diff == -1)[0]  # exclusive
    events = []
    for s, e in zip(starts, ends):
        dur = int(e - s)
        if dur < min_days:
            continue
        seg = values[s:e]
        excess = seg - thr[s:e]
        events.append(
            {
                "start": index[s].strftime("%Y-%m-%d"),
                "end": index[e - 1].strftime("%Y-%m-%d"),
                "year": int(index[s].year),
                "duration": dur,
                "peak_temp": round(float(seg.max()), 1),
                "mean_temp": round(float(seg.mean()), 1),
                "intensity": round(float(excess.mean()), 2),
                "severity": round(float(excess.sum()), 1),
            }
        )
    return events


def yearly_metrics(index: pd.DatetimeIndex, values: np.ndarray, thr: np.ndarray, events: list, start_year: int, end_year: int) -> list:
    years = index.year.to_numpy()
    by_year = {}
    for e in events:
        by_year.setdefault(e["year"], []).append(e)
    rows = []
    for y in range(start_year, end_year + 1):
        mask = years == y
        expected = 366 if calendar.isleap(y) else 365
        v = values[mask]
        t = thr[mask]
        finite = np.isfinite(v)
        valid = int(finite.sum())
        coverage = valid / expected
        ev = by_year.get(y, [])
        durations = [e["duration"] for e in ev]
        rows.append(
            {
                "year": y,
                "events": len(ev),
                "heatwave_days": int(sum(durations)),
                "max_duration": int(max(durations)) if durations else 0,
                "mean_duration": round(float(np.mean(durations)), 2) if durations else 0.0,
                "mean_intensity": round(float(np.mean([e["intensity"] for e in ev])), 2) if ev else None,
                "max_peak": max(e["peak_temp"] for e in ev) if ev else None,
                "hot_days": int(np.sum(finite & (v > t))) if valid else 0,
                "mean_tmax": round(float(v[finite].mean()), 2) if valid else None,
                "coverage": round(coverage, 3),
                "usable": bool(coverage >= MIN_YEAR_COVERAGE),
            }
        )
    return rows
