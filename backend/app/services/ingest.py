"""Weather ingestion with a MongoDB cache in front of the upstream API."""
import hashlib
import json
from datetime import datetime, timezone

from ..config import MODEL_LABEL, settings
from ..db import get_db
from . import openmeteo


def weather_key(points, start_year: int, end_year: int) -> str:
    raw = json.dumps({"p": points, "s": start_year, "e": end_year, "src": "open-meteo-archive:tmax", "model": settings.historical_model}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def get_weather(region, start_year: int, end_year: int):
    """Returns (weather_doc, 'hit' | 'miss'). The raw daily series is cached so reruns never hit the API."""
    points = region.sample_points()
    key = weather_key(points, start_year, end_year)
    db = get_db()
    doc = db.weather_cache.find_one({"key": key}, {"_id": 0})
    if doc:
        return doc, "hit"
    fetched = openmeteo.fetch_daily_tmax(points, f"{start_year}-01-01", f"{end_year}-12-31")
    doc = {
        "key": key,
        "points": [list(p) for p in points],
        "start_year": start_year,
        "end_year": end_year,
        "dates": fetched["dates"],
        "values": fetched["values"],
        "meta": fetched["meta"],
        "source": f"Open-Meteo Historical Weather API ({MODEL_LABEL[settings.historical_model]})",
        "created_at": datetime.now(timezone.utc),
    }
    db.weather_cache.replace_one({"key": key}, doc, upsert=True)
    doc.pop("_id", None)
    return doc, "miss"