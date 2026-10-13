import numpy as np
import pandas as pd
import pytest

from app.services import cleaning, hazards, trends
from app.services.hazards import InsufficientDataError
from tests.synth import make_series


def _idx(n, start="2000-01-01"):
    return pd.date_range(start, periods=n, freq="D")


def test_fixed_threshold_detects_only_runs_of_min_days():
    idx = _idx(2200)
    v = np.full(2200, 20.0)
    v[500:505] = 40.0   # 5-day run -> event
    v[900:902] = 40.0   # 2-day run -> ignored
    thr, summ = hazards.compute_threshold(idx, v, 95, "fixed")
    assert summ["value"] == 20.0
    ev = hazards.detect_events(idx, v, thr, 3)
    assert len(ev) == 1 and ev[0]["duration"] == 5
    assert ev[0]["intensity"] == 20.0 and ev[0]["peak_temp"] == 40.0


def test_missing_day_breaks_a_run():
    idx = _idx(2200)
    v = np.full(2200, 20.0)
    v[500:505] = 40.0
    v[502] = np.nan
    thr, _ = hazards.compute_threshold(idx, v, 95, "fixed")
    assert hazards.detect_events(idx, v, thr, 3) == []


def test_calendar_threshold_runs():
    idx, vals = make_series(messy=False)
    ix = pd.to_datetime(idx)
    thr, summ = hazards.compute_threshold(ix, np.array(vals, float), 95, "calendar")
    assert summ["min"] < summ["max"] and len(thr) == len(ix)


def test_too_little_data_raises():
    idx = _idx(300)
    with pytest.raises(InsufficientDataError):
        hazards.compute_threshold(idx, np.full(300, 20.0), 95, "fixed")


def test_cleaning_reports_and_repairs():
    dates, vals = make_series()
    _, arr, q = cleaning.clean_series(dates, vals)
    assert q["out_of_range_removed"] >= 2
    assert q["spikes_removed"] >= 1
    assert q["interpolated"] >= 2          # the 2-day gap
    assert q["remaining_missing"] >= 12    # the 12-day gap is never bridged
    assert np.nanmax(arr) < 60 and np.nanmin(arr) > -70


def test_cleaning_converts_missing_dates():
    dates, vals = make_series(messy=False)
    del dates[100:110]
    del vals[100:110]
    _, _, q = cleaning.clean_series(dates, vals)
    assert q["missing_dates"] == 10


def test_mann_kendall_known_values():
    x = np.arange(10.0)
    mk = trends.mann_kendall(x, np.arange(1.0, 11.0))
    assert mk["s"] == 45 and mk["tau"] == 1.0
    assert mk["z"] == pytest.approx(44 / np.sqrt(125), abs=1e-3)
    assert mk["sen_slope_per_year"] == pytest.approx(1.0)
    assert mk["trend"] == "increasing" and mk["significant"]


def test_mann_kendall_no_trend_when_constant():
    mk = trends.mann_kendall(np.arange(12.0), np.ones(12))
    assert mk["z"] == 0 and mk["p_value"] == 1.0 and not mk["significant"]


def test_window_change_zero_base_has_no_pct():
    ch = trends.window_change(np.array([0, 0, 0, 0, 0, 0, 1, 2, 3.0]))
    assert ch["pct_change"] is None and ch["abs_change"] > 0


def test_full_pipeline_finds_increase():
    from app.schemas import AnalysisParams, build_region
    from app.services.analysis import compute_analysis

    dates, vals = make_series()
    p = AnalysisParams(build_region(23.0, 72.5, None, None, None, None), 1990, 2020, 95.0, 3, "fixed", "heatwave", "Test")
    doc = compute_analysis(p, {"dates": dates, "values": vals, "meta": {}, "source": "synthetic"})
    hw = doc["trends"]["metrics"]["heatwave_days"]
    assert hw["available"] and hw["mann_kendall"]["significant"]
    assert hw["mann_kendall"]["trend"] == "increasing"
    assert doc["insights"]["headline"]["verdict"] == "significant_increase"
    assert all(e["duration"] >= 3 for e in doc["events"])


def test_matches_independent_slow_implementation():
    """Cross-check the vectorised pipeline against a plain-loop version (same idea as verify_data.py)."""
    from app.schemas import AnalysisParams, build_region
    from app.services.analysis import compute_analysis
    from verify_data import independent_heatwaves

    dates, vals = make_series(messy=False)
    p = AnalysisParams(build_region(23.0, 72.5, None, None, None, None), 1990, 2020, 95.0, 3, "fixed", "heatwave", "T")
    doc = compute_analysis(p, {"dates": dates, "values": vals, "meta": {}, "source": "synthetic"})
    thr, events, per_year = independent_heatwaves(dates, vals, 95.0, 3)
    assert doc["threshold"]["value"] == pytest.approx(thr, abs=0.01)
    assert len(doc["events"]) == len(events)
    for row in doc["yearly"]:
        mine = per_year.get(row["year"], {"events": 0, "heatwave_days": 0})
        assert row["heatwave_days"] == mine["heatwave_days"] and row["events"] == mine["events"]


def test_geocode_understands_city_comma_country(monkeypatch):
    from app.services import openmeteo

    seen = {}

    def fake(url, params, **kw):
        seen.update(params)
        return {"results": [
            {"id": 1, "name": "Bhavnagar", "latitude": 21.77, "longitude": 72.15, "country": "India", "country_code": "IN", "admin1": "Gujarat", "feature_code": "PPLA2"},
            {"id": 2, "name": "Bhavnagar", "latitude": 10.0, "longitude": 20.0, "country": "Elsewhere", "country_code": "EW", "feature_code": "PPL"},
        ]}

    monkeypatch.setattr(openmeteo, "_get_json", fake)
    res = openmeteo.geocode("Bhavnagar, India")
    assert seen["name"] == "Bhavnagar"          # the provider only sees the place name
    assert len(res) == 1 and res[0]["label"] == "Bhavnagar, Gujarat, India"
    assert len(openmeteo.geocode("Bhavnagar")) == 2
    assert len(openmeteo.geocode("Bhavnagar, Narnia")) == 2  # unmatched hint never hides the name matches