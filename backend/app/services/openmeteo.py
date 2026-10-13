"""Open-Meteo client: ERA5-based daily maximum temperature + place search.

Safety: only fixed, allow-listed hosts are ever contacted (no user-supplied URLs -> no SSRF),
redirects are not followed, responses are size-capped, and transient errors are retried with backoff.
"""
import time
from typing import List, Tuple
from urllib.parse import urlparse

import httpx
import pandas as pd

from ..config import settings

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
ALLOWED_HOSTS = {"archive-api.open-meteo.com", "geocoding-api.open-meteo.com"}
MAX_RESPONSE_BYTES = 25 * 1024 * 1024
USER_AGENT = "heatline-climate-analyzer/1.0"


class UpstreamError(RuntimeError):
    """The weather provider failed or rejected the request."""


def _get_json(url: str, params: dict, timeout: float = 60.0, retries: int = 3) -> dict:
    if urlparse(url).hostname not in ALLOWED_HOSTS:
        raise UpstreamError("Blocked outbound request to a non-allow-listed host.")
    last = "unknown error"
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False, headers={"User-Agent": USER_AGENT}) as client:
                resp = client.get(url, params=params)
            if resp.status_code == 429 or resp.status_code >= 500:
                last = f"HTTP {resp.status_code}"
            elif resp.status_code >= 400:
                reason = ""
                try:
                    reason = resp.json().get("reason", "")
                except Exception:
                    pass
                raise UpstreamError(f"Weather provider rejected the request: {reason or resp.status_code}")
            else:
                if len(resp.content) > MAX_RESPONSE_BYTES:
                    raise UpstreamError("Weather provider response was unexpectedly large.")
                try:
                    return resp.json()
                except ValueError:
                    last = "invalid JSON"
        except httpx.HTTPError as exc:
            last = type(exc).__name__
        if attempt < retries - 1:
            time.sleep(min(2 ** attempt, 6))
    raise UpstreamError(f"Weather provider is unavailable ({last}). Please try again in a moment.")


def _to_celsius(values, unit: str):
    u = (unit or "").strip()
    if u in ("°F", "F", "fahrenheit"):
        return [None if v is None else (v - 32.0) * 5.0 / 9.0 for v in values]
    if u in ("K", "kelvin"):
        return [None if v is None else v - 273.15 for v in values]
    return list(values)


def fetch_daily_tmax(points: List[Tuple[float, float]], start_date: str, end_date: str) -> dict:
    """Daily max 2 m temperature (deg C), averaged over the sampled grid points."""
    params = {
        "latitude": ",".join(f"{p[0]:.2f}" for p in points),
        "longitude": ",".join(f"{p[1]:.2f}" for p in points),
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_max",
        "models": settings.historical_model,
        "temperature_unit": "celsius",
        "timezone": "auto",
    }
    data = _get_json(ARCHIVE_URL, params)
    responses = data if isinstance(data, list) else [data]
    series = []
    grid, units_in, elevations = [], None, []
    for r in responses:
        daily = r.get("daily") or {}
        key = next((k for k in daily if k == "temperature_2m_max" or k.startswith("temperature_2m_max_")), None)
        if "time" not in daily or key is None:
            raise UpstreamError("Weather provider returned an unexpected response shape.")
        units_in = (r.get("daily_units") or {}).get(key, "°C")
        vals = _to_celsius(daily[key], units_in)
        series.append(pd.Series(vals, index=pd.to_datetime(daily["time"]), dtype=float))
        grid.append([r.get("latitude"), r.get("longitude")])
        if r.get("elevation") is not None:
            elevations.append(r["elevation"])
    merged = pd.concat(series, axis=1).mean(axis=1, skipna=True)
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in merged.index],
        "values": [None if pd.isna(v) else round(float(v), 2) for v in merged.to_numpy()],
        "meta": {"units_in": units_in, "grid": grid, "elevation": elevations},
    }


def _split_query(q: str):
    """'Bhavnagar, India' -> ('Bhavnagar', ['india']). The provider only matches the place name,
    so the part after a comma is used as a hint to rank or filter the results instead."""
    parts = [p.strip() for p in q.split(",") if p.strip()]
    if not parts:
        return q.strip(), []
    return parts[0], [h.lower() for h in parts[1:]]


def geocode(q: str, count: int = 8) -> list:
    name_q, hints = _split_query(q)
    data = _get_json(GEOCODE_URL, {"name": name_q, "count": 20 if hints else count, "language": "en", "format": "json"}, timeout=20.0, retries=2)
    out = []
    for r in data.get("results") or []:
        try:
            lat, lon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        fc = r.get("feature_code") or ""
        name, admin1, country = r.get("name"), r.get("admin1"), r.get("country")
        parts = [name]
        if admin1 and admin1 != name:
            parts.append(admin1)
        if country:
            parts.append(country)
        hay = " ".join(str(r.get(k) or "") for k in ("name", "admin1", "admin2", "country", "country_code")).lower()
        item = {
            "id": r.get("id"),
            "name": name,
            "label": ", ".join(p for p in parts if p),
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "kind": "state" if fc.startswith("ADM1") else "city",
            "_match": all(h in hay for h in hints),
        }
        if item["kind"] == "state":
            # Open-Meteo gives a centroid only, so a state is approximated by a 2x2 degree box around it.
            item["box"] = {
                "south": round(max(-90.0, lat - 1.0), 2),
                "north": round(min(90.0, lat + 1.0), 2),
                "west": round(max(-180.0, lon - 1.0), 2),
                "east": round(min(180.0, lon + 1.0), 2),
            }
        out.append(item)
    if hints:
        matched = [i for i in out if i["_match"]]
        out = matched or out  # if the hint matches nothing, still show the name matches
    for i in out:
        i.pop("_match", None)
    return out[:count]