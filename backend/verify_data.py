"""Independent check of the app's numbers.

It downloads the raw daily maximum temperature straight from Open-Meteo, counts heatwaves with plain
Python loops (no pandas, none of the app's code), then compares the result with what your running
backend returns. If the two agree, the pipeline is doing what it says.

Usage (backend must be running on port 8000):
    python verify_data.py --lat 21.76 --lon 72.15 --start 1990 --end 2020
Options: --percentile 95 --min-days 3 --api http://localhost:8000
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request

import numpy as np


def independent_heatwaves(dates, values, percentile=95.0, min_days=3):
    """Fixed-threshold heatwaves, written the slow obvious way. Returns (threshold, events, per_year)."""
    valid = [v for v in values if v is not None]
    thr = float(np.percentile(valid, percentile))
    events, run = [], []
    for d, v in zip(dates, values):
        if v is not None and v > thr:
            run.append(d)
        else:  # a missing day also ends a run
            if len(run) >= min_days:
                events.append((run[0], len(run)))
            run = []
    if len(run) >= min_days:
        events.append((run[0], len(run)))
    per_year = {}
    for start, length in events:
        y = int(start[:4])
        a = per_year.setdefault(y, {"events": 0, "heatwave_days": 0})
        a["events"] += 1
        a["heatwave_days"] += length
    return thr, events, per_year


def independent_sen_per_decade(years, values):
    """Sen's slope per decade with plain loops: the median of every pairwise slope, times 10."""
    slopes = []
    for i in range(len(years)):
        for j in range(i + 1, len(years)):
            slopes.append((values[j] - values[i]) / (years[j] - years[i]))
    slopes.sort()
    n = len(slopes)
    mid = slopes[n // 2] if n % 2 else (slopes[n // 2 - 1] + slopes[n // 2]) / 2
    return mid * 10


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "heatline-verify/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--start", type=int, default=1990)
    ap.add_argument("--end", type=int, default=2020)
    ap.add_argument("--percentile", type=float, default=95.0)
    ap.add_argument("--min-days", type=int, default=3)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--model", default="era5_land", help="must match HISTORICAL_MODEL of the backend (era5_land or era5)")
    a = ap.parse_args()
    lat, lon = round(a.lat, 2), round(a.lon, 2)

    q = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "start_date": f"{a.start}-01-01", "end_date": f"{a.end}-12-31",
                                "daily": "temperature_2m_max", "models": a.model, "timezone": "auto"})
    raw = _get(f"https://archive-api.open-meteo.com/v1/archive?{q}")
    dates, values = raw["daily"]["time"], raw["daily"]["temperature_2m_max"]
    print(f"Raw data: {len(dates)} days from Open-Meteo, grid cell {raw.get('latitude')}, {raw.get('longitude')}, missing: {sum(v is None for v in values)}")
    print("First 5 days (compare these with open-meteo.com if you like):")
    for d, v in list(zip(dates, values))[:5]:
        print(f"  {d}  {v} C")

    thr, events, per_year = independent_heatwaves(dates, values, a.percentile, a.min_days)
    print(f"\nIndependent result: threshold {thr:.2f} C, {len(events)} events")

    api_q = urllib.parse.urlencode({"lat": lat, "lon": lon, "start_year": a.start, "end_year": a.end, "percentile": a.percentile,
                                    "min_days": a.min_days, "method": "fixed"})
    doc = _get(f"{a.api}/api/analysis?{api_q}")
    print(f"App result:         threshold {doc['threshold']['value']:.2f} C, {len(doc['events'])} events\n")

    print(f"{'Year':<6}{'HW days (me)':>14}{'HW days (app)':>15}{'Events (me)':>13}{'Events (app)':>14}  OK")
    bad = 0
    for row in doc["yearly"]:
        y = row["year"]
        mine = per_year.get(y, {"events": 0, "heatwave_days": 0})
        ok = mine["heatwave_days"] == row["heatwave_days"] and mine["events"] == row["events"]
        bad += 0 if ok else 1
        print(f"{y:<6}{mine['heatwave_days']:>14}{row['heatwave_days']:>15}{mine['events']:>13}{row['events']:>14}  {'yes' if ok else 'DIFF'}")

    rob = doc.get("robustness")
    rob_bad = 0
    if rob:
        usable = [r["year"] for r in doc["yearly"] if r["usable"]]
        print("\nRobustness grid: every definition recounted independently")
        print(f"{'Percentile':<12}{'Min days':>9}{'Events (me)':>13}{'Events (app)':>14}{'HW days (me)':>14}{'HW days (app)':>15}{'Sen/dec (me)':>14}{'Sen/dec (app)':>15}  OK")
        for c in rob["cells"]:
            _, ev_c, py_c = independent_heatwaves(dates, values, c["percentile"], c["min_days"])
            days_c = [py_c.get(y, {"heatwave_days": 0})["heatwave_days"] for y in usable]
            sen_me = independent_sen_per_decade(usable, days_c) if len(usable) >= 8 else None
            ok = len(ev_c) == c["events"] and sum(days_c) == c["heatwave_days"]
            if sen_me is not None and c["sen_per_decade"] is not None:
                ok = ok and abs(sen_me - c["sen_per_decade"]) < 0.01
            rob_bad += 0 if ok else 1
            fmt = lambda v: "-" if v is None else f"{v:+.2f}"
            print(f"{c['percentile']:<12g}{c['min_days']:>9}{len(ev_c):>13}{c['events']:>14}{sum(days_c):>14}{c['heatwave_days']:>15}{fmt(sen_me):>14}{fmt(c['sen_per_decade']):>15}  {'yes' if ok else 'DIFF'}")
        print(f"App verdict: {rob['summary']['text']}")

    q = doc["quality"]
    print(f"\nApp cleaning: {q['interpolated']} filled, {q['out_of_range_removed']} impossible, {q['spikes_removed']} spikes, {q['remaining_missing']} still missing")
    bad += rob_bad
    if bad == 0:
        print("RESULT: all years match." if not rob else "RESULT: all years and all robustness cells match.")
    else:
        print(f"RESULT: {bad} row(s) differ. Small differences are expected only if the app's cleaning changed some days (see counts above).")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())