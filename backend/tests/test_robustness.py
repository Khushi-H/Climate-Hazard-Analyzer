"""Tests for the robustness check (does the headline trend survive a change of definition?)."""
import numpy as np
import pytest
from scipy import stats

from app import db as dbmod
from app.main import app
from app.schemas import AnalysisParams, build_region
from app.security import reset_limiters
from app.services import cleaning, exports, openmeteo, robustness
from app.services.analysis import compute_analysis
from tests.synth import make_series
from verify_data import independent_heatwaves

REGION = build_region(23.0, 72.5, None, None, None, None)


def _doc(percentile=95.0, min_days=3, method="fixed", messy=False, warming=0.04, start=1990, end=2020):
    dates, vals = make_series(start, end, messy=messy, warming=warming)
    p = AnalysisParams(REGION, start, end, percentile, min_days, method, "heatwave", "Test")
    return compute_analysis(p, {"dates": dates, "values": vals, "meta": {}, "source": "synthetic"}), dates, vals


def _cell(doc, percentile, min_days):
    return next(c for c in doc["robustness"]["cells"] if c["percentile"] == percentile and c["min_days"] == min_days)


def test_default_grid_is_3x3_and_marks_exactly_the_users_setting():
    doc, _, _ = _doc()
    rob = doc["robustness"]
    assert rob["percentiles"] == [90.0, 95.0, 97.0] and rob["min_days"] == [2, 3, 5]
    assert len(rob["cells"]) == 9
    current = [c for c in rob["cells"] if c["current"]]
    assert len(current) == 1 and (current[0]["percentile"], current[0]["min_days"]) == (95.0, 3)


def test_grid_always_contains_a_setting_that_is_not_on_the_default_grid():
    doc, _, _ = _doc(percentile=92.0, min_days=4)
    rob = doc["robustness"]
    assert 92.0 in rob["percentiles"] and 4 in rob["min_days"]
    assert len(rob["cells"]) == len(rob["percentiles"]) * len(rob["min_days"]) == 16
    assert sum(c["current"] for c in rob["cells"]) == 1


def test_current_cell_equals_the_headline_analysis():
    """The cell for the user's own setting must reproduce the main result exactly."""
    doc, _, _ = _doc()
    c = _cell(doc, 95.0, 3)
    hw = doc["trends"]["metrics"]["heatwave_days"]
    assert c["events"] == len(doc["events"])
    assert c["threshold"] == doc["threshold"]["value"]
    assert c["sen_per_decade"] == hw["mann_kendall"]["sen_slope_per_decade"]
    assert c["p_value"] == hw["mann_kendall"]["p_value"]
    assert c["pct_change"] == hw["change"]["pct_change"]


def test_every_cell_matches_an_independent_plain_loop_implementation():
    """Recount each cell with plain Python loops and scipy's own Theil-Sen / Kendall (none of the app's trend code)."""
    doc, dates, vals = _doc(warming=0.06)
    # the app cleans first (3 isolated spikes are repaired in this series), so recount on the same cleaned days;
    # cleaning has its own tests, what is under test here is the threshold, the run detection and the trend statistics
    idx, arr, _ = cleaning.clean_series(dates, vals)
    dates = [d.strftime("%Y-%m-%d") for d in idx]
    vals = [None if np.isnan(x) else float(x) for x in arr]
    years = [r["year"] for r in doc["yearly"] if r["usable"]]
    checked = 0
    for c in doc["robustness"]["cells"]:
        thr, events, per_year = independent_heatwaves(dates, vals, c["percentile"], c["min_days"])
        assert c["threshold"] == pytest.approx(thr, abs=0.01)
        assert c["events"] == len(events)
        days = [per_year.get(y, {"heatwave_days": 0})["heatwave_days"] for y in years]
        assert c["heatwave_days"] == sum(days)
        assert c["available"]
        slope = stats.theilslopes(days, years)[0] * 10
        assert c["sen_per_decade"] == pytest.approx(slope, abs=0.01)
        tau, p = stats.kendalltau(years, days)
        assert np.sign(c["tau"]) == np.sign(tau)
        assert c["p_value"] == pytest.approx(p, abs=0.03)  # ours uses the continuity correction, scipy's asymptotic p does not
        checked += 1
    assert checked == 9


def test_stricter_definitions_have_fewer_events_and_are_flagged_when_few():
    doc, _, _ = _doc()
    loose = _cell(doc, 90.0, 2)
    strict = _cell(doc, 97.0, 5)
    assert strict["events"] < loose["events"]
    assert strict["few_events"] == (strict["events"] < robustness.FEW_EVENTS)


def test_calendar_method_also_produces_a_grid():
    doc, _, _ = _doc(method="calendar")
    assert len(doc["robustness"]["cells"]) == 9
    assert all(c["available"] for c in doc["robustness"]["cells"])


def _fake(trend, slope, available=True):
    return {"available": available, "trend": trend, "sen_per_decade": slope}


def test_summary_consistent_mostly_mixed_and_unavailable():
    inc = [_fake("increasing", 5.0 + i) for i in range(9)]
    s = robustness.summarise(inc)
    assert s["verdict"] == "consistent" and s["dominant"] == "increasing" and s["n"] == 9
    assert s["slope_min"] == 5.0 and s["slope_max"] == 13.0 and "All 9 definitions" in s["text"]

    mostly = [_fake("increasing", 4.0)] * 7 + [_fake("no significant trend", 0.5)] * 2
    s = robustness.summarise(mostly)
    assert s["verdict"] == "mostly" and s["increasing"] == 7 and s["no_trend"] == 2
    assert "7 of 9" in s["text"]

    mixed = [_fake("increasing", 3.0)] * 3 + [_fake("no significant trend", 0.1)] * 3 + [_fake("decreasing", -2.0)] * 3
    s = robustness.summarise(mixed)
    assert s["verdict"] == "mixed" and "inconclusive" in s["text"]

    s = robustness.summarise([_fake(None, None, available=False)] * 4)
    assert s["verdict"] == "unavailable" and s["n"] == 0 and s["total"] == 4


def test_summary_counts_unusable_cells_separately():
    cells = [_fake("increasing", 2.0)] * 3 + [_fake(None, None, available=False)]
    s = robustness.summarise(cells)
    assert s["n"] == 3 and s["total"] == 4 and s["verdict"] == "consistent"


def test_robustness_failure_never_breaks_the_analysis(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(robustness, "_cell", boom)
    dates, vals = make_series(messy=False)
    p = AnalysisParams(REGION, 1990, 2020, 95.0, 3, "fixed", "heatwave", "T")
    doc = compute_analysis(p, {"dates": dates, "values": vals, "meta": {}, "source": "synthetic"})
    assert doc["robustness"] is None and doc["yearly"] and doc["insights"]["headline"]["text"]


def test_pdf_renders_with_and_without_the_robustness_section():
    doc, _, _ = _doc()
    with_rob = exports.render_pdf(doc)
    assert with_rob.startswith(b"%PDF")
    doc2 = dict(doc, robustness=None, key=doc["key"] + "-none")
    without = exports.render_pdf(doc2)
    assert without.startswith(b"%PDF") and len(with_rob) != len(without)


@pytest.fixture()
def client(monkeypatch):
    dbmod.reset_for_tests()
    reset_limiters()
    monkeypatch.setattr(openmeteo, "fetch_daily_tmax", lambda points, start, end: {
        "dates": make_series(int(start[:4]), int(end[:4]))[0], "values": make_series(int(start[:4]), int(end[:4]))[1],
        "meta": {"units_in": "°C", "grid": [], "elevation": []}})
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


def test_api_returns_the_robustness_grid_and_serves_it_from_the_database(client):
    q = "lat=23.02&lon=72.57&start_year=1990&end_year=2020&name=Test"
    j1 = client.get(f"/api/analysis?{q}").json()
    assert j1["cache"]["analysis"] == "miss"
    rob = j1["robustness"]
    assert len(rob["cells"]) == 9 and rob["summary"]["verdict"] in {"consistent", "mostly", "mixed"}
    j2 = client.get(f"/api/analysis?{q}").json()
    assert j2["cache"]["analysis"] == "hit" and j2["robustness"] == rob


def test_ordinal_wording():
    from app.services.text import ordinal
    assert [ordinal(n) for n in (90, 92, 95, 97, 99, 91, 93, 11, 12, 13, 111)] == [
        "90th", "92nd", "95th", "97th", "99th", "91st", "93rd", "11th", "12th", "13th", "111th"]
    assert ordinal(92.5) == "92.5th"