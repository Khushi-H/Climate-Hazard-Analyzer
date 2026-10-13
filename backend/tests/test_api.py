import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app.main import app
from app.security import reset_limiters
from app.services import openmeteo
from tests.synth import make_series

calls = {"n": 0}


@pytest.fixture()
def client(monkeypatch):
    dbmod.reset_for_tests()
    reset_limiters()
    calls["n"] = 0

    def fake_fetch(points, start, end):
        calls["n"] += 1
        d, v = make_series(int(start[:4]), int(end[:4]))
        return {"dates": d, "values": v, "meta": {"units_in": "°C", "grid": [], "elevation": []}}

    monkeypatch.setattr(openmeteo, "fetch_daily_tmax", fake_fetch)
    monkeypatch.setattr(openmeteo, "geocode", lambda q, count=8: [{"label": q, "lat": 1.0, "lon": 2.0, "kind": "city"}])
    with TestClient(app) as c:
        yield c


Q = "lat=23.02&lon=72.57&start_year=1990&end_year=2020&name=Test"


def test_health_and_meta(client):
    assert client.get("/api/health").json()["status"] == "ok"
    m = client.get("/api/meta").json()
    assert m["hazards"][0]["id"] == "heatwave" and m["hazards"][0]["available"]


def test_analysis_caches_and_reads_from_db(client):
    r1 = client.get(f"/api/analysis?{Q}")
    assert r1.status_code == 200
    j = r1.json()
    assert j["cache"]["analysis"] == "miss" and j["cache"]["weather"] == "miss"
    assert len(j["yearly"]) == 31 and j["insights"]["headline"]["text"]
    r2 = client.get(f"/api/analysis?{Q}")
    assert r2.json()["cache"]["analysis"] == "hit"
    assert calls["n"] == 1  # upstream hit once only
    # etag -> 304
    r3 = client.get(f"/api/analysis?{Q}", headers={"If-None-Match": r2.headers["etag"]})
    assert r3.status_code == 304


def test_box_region_and_calendar_method(client):
    r = client.get("/api/analysis?south=22&west=71&north=24&east=73&start_year=1990&end_year=2020&method=calendar")
    assert r.status_code == 200 and r.json()["region"]["kind"] == "box"


@pytest.mark.parametrize("qs", [
    "lat=999&lon=0",
    "lat=10",
    "lat=10&lon=10&start_year=2000&end_year=2005",
    "lat=10&lon=10&end_year=2999",
    "south=0&west=0&north=40&east=40",
    "south=5&west=5&north=1&east=9",
    "lat=10&lon=10&percentile=10",
    "lat=10&lon=10&hazard=drought",
    "lat=nan&lon=10",
])
def test_bad_input_rejected(client, qs):
    assert client.get(f"/api/analysis?{qs}").status_code == 422


def test_exports(client):
    csv_r = client.get(f"/api/analysis/export.csv?{Q}&kind=yearly")
    assert csv_r.status_code == 200 and csv_r.text.startswith("year,events")
    assert "attachment" in csv_r.headers["content-disposition"]
    assert client.get(f"/api/analysis/export.csv?{Q}&kind=events").text.startswith("start,end")
    pdf = client.get(f"/api/analysis/export.pdf?{Q}")
    assert pdf.content[:4] == b"%PDF"
    png = client.get(f"/api/analysis/plot.png?{Q}&metric=events")
    assert png.content[:4] == b"\x89PNG"


def test_label_with_markup_is_sanitised(client):
    r = client.get("/api/analysis?lat=10&lon=10&start_year=1990&end_year=2020&name=%3Cscript%3Ealert(1)%3C/script%3E")
    assert "<" not in r.json()["region"]["name"]


def test_geocode(client):
    assert client.get("/api/geocode?q=Delhi").json()["results"][0]["label"] == "Delhi"
    assert client.get("/api/geocode?q=a").status_code == 422


def test_rate_limit(client):
    from app.security import heavy_limiter

    codes = [client.get(f"/api/analysis?{Q}").status_code for _ in range(heavy_limiter.limit + 3)]
    assert codes[-1] == 429


def test_upstream_failure_returns_502(client, monkeypatch):
    def boom(*a, **k):
        raise openmeteo.UpstreamError("down")

    monkeypatch.setattr(openmeteo, "fetch_daily_tmax", boom)
    r = client.get("/api/analysis?lat=11&lon=11&start_year=1990&end_year=2020")
    assert r.status_code == 502 and "down" in r.json()["detail"]


def test_archive_request_pins_one_homogeneous_model(monkeypatch):
    """Regression: the default 'best match' switches model in 2017 and fakes a trend."""
    from app.config import settings
    from app.services import ingest, openmeteo

    seen = {}

    def fake(url, params, **kw):
        seen.update(params)
        return {"daily": {"time": ["2000-01-01"], "temperature_2m_max": [30.0]}, "daily_units": {"temperature_2m_max": "°C"}, "latitude": 1, "longitude": 2}

    monkeypatch.setattr(openmeteo, "_get_json", fake)
    openmeteo.fetch_daily_tmax([(21.76, 72.15)], "2000-01-01", "2000-01-01")
    assert seen["models"] == settings.historical_model == "era5_land"

    k1 = ingest.weather_key([(1.0, 2.0)], 2000, 2020)
    monkeypatch.setattr(settings, "historical_model", "era5")
    assert ingest.weather_key([(1.0, 2.0)], 2000, 2020) != k1  # old cached best-match data is never reused