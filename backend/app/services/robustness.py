"""Robustness check: does the headline trend survive a change of definition?

A heatwave needs two choices that have no single correct value: how hot is "hot" (the percentile) and how long
is a "wave" (the minimum number of days in a row). A trend that only appears for one convenient pair of values
is not a finding. So the same cleaned record is re-analysed on a small grid of both choices, and the trend in
heatwave days per year is tested every time (Mann-Kendall test and Sen's slope, the same statistics as the
headline). If every cell agrees the result does not depend on the definition; if they disagree, the headline
should be read with care.

The grid always contains the user's own setting, so it can be marked as "your setting" in the interface.
No extra data is downloaded: the cleaned series from the main analysis is reused.
"""
import logging

from . import hazards, trends
from .hazards import InsufficientDataError

log = logging.getLogger("heatline.robustness")

PERCENTILES = (90.0, 95.0, 97.0)
MIN_DAYS = (2, 3, 5)
FEW_EVENTS = 10  # under this many events a trend estimate is fragile, so the cell is flagged

_PHRASE = {
    "increasing": "a statistically significant increase",
    "decreasing": "a statistically significant decrease",
    "no_trend": "no statistically significant trend",
}


def _kind(cell) -> str:
    if cell["trend"] == "increasing":
        return "increasing"
    if cell["trend"] == "decreasing":
        return "decreasing"
    return "no_trend"


def summarise(cells: list) -> dict:
    """Plain-language verdict over all usable cells. Pure function so it can be tested on its own."""
    ok = [c for c in cells if c["available"]]
    n = len(ok)
    counts = {"increasing": 0, "decreasing": 0, "no_trend": 0}
    for c in ok:
        counts[_kind(c)] += 1
    out = {
        "n": n,
        "total": len(cells),
        "increasing": counts["increasing"],
        "decreasing": counts["decreasing"],
        "no_trend": counts["no_trend"],
        "slope_min": None,
        "slope_max": None,
        "dominant": None,
        "verdict": "unavailable",
        "text": "There are not enough usable years to compare different definitions of a heatwave.",
    }
    if n == 0:
        return out

    slopes = [c["sen_per_decade"] for c in ok]
    lo, hi = min(slopes), max(slopes)
    dominant = max(counts, key=lambda k: counts[k])
    top = counts[dominant]
    share = top / n
    parts = [f"{counts[k]} {'finds' if counts[k] == 1 else 'find'} {_PHRASE[k]}" for k in ("increasing", "no_trend", "decreasing") if counts[k]]
    out.update(slope_min=lo, slope_max=hi, dominant=dominant)

    if share == 1:
        out["verdict"] = "consistent"
        out["text"] = (f"{'The only definition' if n == 1 else f'All {n} definitions'} tested {'shows' if n == 1 else 'agree:'} {_PHRASE[dominant]} in heatwave days "
                       f"(Sen's slope {lo:+.1f} to {hi:+.1f} days per decade).")
    elif share >= 0.75:
        out["verdict"] = "mostly"
        out["text"] = (f"{top} of {n} definitions find {_PHRASE[dominant]}, but not all of them agree ({'; '.join(parts)}). "
                       f"Sen's slope ranges from {lo:+.1f} to {hi:+.1f} days per decade.")
    else:
        out["verdict"] = "mixed"
        out["text"] = (f"The answer depends on the definition: {'; '.join(parts)}. "
                       f"Treat the headline trend as inconclusive.")
    return out


def _grid(defaults, current):
    return sorted(set(defaults) | {current})


def _cell(index, values, thr, thr_value, percentile, min_days, params) -> dict:
    events = hazards.detect_events(index, values, thr, min_days)
    yearly = hazards.yearly_metrics(index, values, thr, events, params.start_year, params.end_year)
    hw = trends.build_trends(yearly)["metrics"]["heatwave_days"]
    cell = {
        "percentile": percentile,
        "min_days": min_days,
        "current": percentile == round(float(params.percentile), 2) and min_days == int(params.min_days),
        "threshold": thr_value,
        "events": len(events),
        "heatwave_days": int(sum(r["heatwave_days"] for r in yearly)),
        "few_events": len(events) < FEW_EVENTS,
        "available": bool(hw.get("available")),
        "trend": None,
        "significant": None,
        "sen_per_decade": None,
        "p_value": None,
        "tau": None,
        "pct_change": None,
    }
    if cell["available"]:
        mk = hw["mann_kendall"]
        cell.update(
            trend=mk["trend"],
            significant=bool(mk["significant"]),
            sen_per_decade=mk["sen_slope_per_decade"],
            p_value=mk["p_value"],
            tau=mk["tau"],
            pct_change=hw["change"]["pct_change"],
        )
    return cell


def compute_robustness(index, values, params):
    """Grid of (percentile x minimum days). Returns None if it cannot be computed; it must never block the analysis."""
    percentiles = _grid(PERCENTILES, round(float(params.percentile), 2))
    min_days = _grid(MIN_DAYS, int(params.min_days))
    cells = []
    try:
        for p in percentiles:
            thr, summary = hazards.compute_threshold(index, values, p, params.method)
            for d in min_days:
                cells.append(_cell(index, values, thr, summary["value"], p, d, params))
    except InsufficientDataError:
        return None
    except Exception:  # pragma: no cover - a failed extra must not take the main result down
        log.exception("Robustness check failed")
        return None
    return {"percentiles": percentiles, "min_days": min_days, "cells": cells, "summary": summarise(cells)}