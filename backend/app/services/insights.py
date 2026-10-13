"""Plain-language, honest summaries. Significance is always stated; weak evidence is labelled as such."""
from .text import ordinal



def _fmt(x, d=1):
    return f"{x:.{d}f}"


def _p(p):
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def build_insights(params, yearly, trends, events, threshold, quality, excluded_years) -> dict:
    hw = trends["metrics"]["heatwave_days"]
    bullets, caveats = [], []
    headline = {"metric": "heatwave_days", "verdict": "insufficient_data", "pct": None, "abs_change": None,
                "first_mean": None, "last_mean": None, "window_years": None, "p_value": None,
                "text": "There are not enough complete years of data to estimate a heatwave trend for this region and period."}

    if hw.get("available"):
        ch, mk = hw["change"], hw["mann_kendall"]
        k, pct = ch["window_years"], ch["pct_change"]
        sig = bool(mk and mk["significant"])
        direction = "increased" if ch["abs_change"] > 0 else "decreased" if ch["abs_change"] < 0 else "not changed"
        if pct is not None and direction != "not changed":
            core = (f"Heatwave days {direction} by {abs(pct):.0f}%, from {_fmt(ch['first_mean'])} days per year in the first {k} years "
                    f"to {_fmt(ch['last_mean'])} in the last {k}.")
        else:
            core = (f"Heatwave days per year went from {_fmt(ch['first_mean'])} in the first {k} years to {_fmt(ch['last_mean'])} in the last {k}"
                    f" (the starting level is zero, so a percentage change is not defined).")
        if sig:
            verdict = "significant_increase" if mk["z"] > 0 else "significant_decrease"
            tail = f" The Mann-Kendall test finds this trend statistically significant ({_p(mk['p_value'])})."
        else:
            verdict = "not_significant"
            tail = (f" However, the Mann-Kendall test does not find a statistically significant trend ({_p(mk['p_value'])}), "
                    f"so treat this change as inconclusive.")
        headline.update(verdict=verdict, pct=pct, abs_change=ch["abs_change"], first_mean=ch["first_mean"],
                        last_mean=ch["last_mean"], window_years=k, p_value=mk["p_value"], text=core + tail)

        bullets.append(f"Sen's slope for heatwave days is {mk['sen_slope_per_decade']:+.2f} days per decade; ordinary regression gives "
                       f"{hw['linear']['slope_per_decade']:+.2f} per decade (R2 = {hw['linear']['r2']:.2f}).")
        ev = trends["metrics"]["events"]
        if ev.get("available"):
            bullets.append(f"Number of heatwave events per year changed by {ev['mann_kendall']['sen_slope_per_decade']:+.2f} per decade (Sen's slope; "
                           f"{'significant' if ev['mann_kendall']['significant'] else 'not significant'}, {_p(ev['mann_kendall']['p_value'])}).")
        it = trends["metrics"]["mean_intensity"]
        if it.get("available"):
            bullets.append(f"Mean intensity (average degrees above threshold during events) changed by {it['mann_kendall']['sen_slope_per_decade']:+.2f} deg C per decade "
                           f"(Sen's slope; {'significant' if it['mann_kendall']['significant'] else 'not significant'}).")
        if ch["small_base"] and pct is not None:
            caveats.append("The starting level is under 1 heatwave day per year, so the percentage change looks large for a small absolute change.")

    if events:
        longest = max(events, key=lambda e: e["duration"])
        hottest = max(events, key=lambda e: e["peak_temp"])
        bullets.append(f"Longest event: {longest['duration']} days starting {longest['start']}. Hottest peak: {hottest['peak_temp']} deg C on an event starting {hottest['start']}.")
    usable_rows = [r for r in yearly if r["usable"]]
    if usable_rows:
        worst = max(usable_rows, key=lambda r: r["heatwave_days"])
        if worst["heatwave_days"] > 0:
            bullets.append(f"{worst['year']} had the most heatwave days ({worst['heatwave_days']}).")

    method_txt = ("a single threshold for the whole period" if threshold["method"] == "fixed"
                  else "a separate threshold for each day of the year (+-7 day window)")
    bullets.append(f"A heatwave day means a daily maximum above the {ordinal(params.percentile)} percentile "
                   f"({threshold['value']} deg C on average; {method_txt}) on at least {params.min_days} days in a row.")

    n_years = params.end_year - params.start_year + 1
    if n_years < 30:
        caveats.append(f"The record is only {n_years} years long. Trends over fewer than about 30 years are sensitive to natural variability such as El Nino and La Nina.")
    caveats.append("The percentile threshold is calculated from the same period that is analysed, so the results describe change within this period, not change relative to a pre-industrial or official baseline.")
    caveats.append("Data comes from a reanalysis grid (about 9-25 km). It smooths local extremes and does not capture urban heat islands, so values can differ from a station thermometer.")
    if len(events) < 10:
        caveats.append(f"Only {len(events)} events were detected in total. Small samples make trend estimates fragile.")
    if excluded_years:
        caveats.append(f"{len(excluded_years)} year(s) with under 80% valid data were excluded from the trend: {', '.join(map(str, excluded_years[:12]))}.")
    if quality["interpolated"] or quality["out_of_range_removed"] or quality["spikes_removed"]:
        caveats.append(f"Data cleaning: {quality['interpolated']} short-gap day(s) interpolated, {quality['out_of_range_removed']} impossible value(s) and "
                       f"{quality['spikes_removed']} spike(s) removed. Long gaps were left missing and never counted as hot.")
    caveats.append("Heatwaves are attributed to the year in which they start.")
    return {"headline": headline, "bullets": bullets, "caveats": caveats}