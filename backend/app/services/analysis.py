"""Orchestration: cache -> ingest -> clean -> detect -> trend -> store -> read back from the database."""
import threading
from collections import defaultdict
from datetime import datetime, timezone

from ..config import ALGO_VERSION
from ..db import get_db
from ..utils import to_native
from . import cleaning, hazards, ingest, robustness, trends
from .insights import build_insights

_locks = defaultdict(threading.Lock)
_locks_guard = threading.Lock()


def _lock_for(key: str):
    with _locks_guard:
        return _locks[key]


def compute_analysis(params, weather: dict) -> dict:
    """Pure computation (no I/O) so it can be unit-tested with synthetic data."""
    index, values, quality = cleaning.clean_series(weather["dates"], weather["values"])
    thr_series, thr_summary = hazards.compute_threshold(index, values, params.percentile, params.method)
    events = hazards.detect_events(index, values, thr_series, params.min_days)
    yearly = hazards.yearly_metrics(index, values, thr_series, events, params.start_year, params.end_year)
    tr = trends.build_trends(yearly)
    rob = robustness.compute_robustness(index, values, params)
    excluded = [r["year"] for r in yearly if not r["usable"]]
    insights = build_insights(params, yearly, tr, events, thr_summary, quality, excluded)
    doc = {
        "key": params.key(),
        "params": params.to_dict(),
        "region": params.region.to_dict(),
        "threshold": thr_summary,
        "quality": quality,
        "excluded_years": excluded,
        "yearly": yearly,
        "events": events,
        "trends": tr,
        "robustness": rob,
        "insights": insights,
        "meta": {
            "source": weather.get("source", "Open-Meteo"),
            "algo_version": ALGO_VERSION,
            "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "upstream": weather.get("meta", {}),
        },
        "created_at": datetime.now(timezone.utc),
    }
    return to_native(doc)


def get_analysis(params):
    """Always serves what is stored in MongoDB. Returns (doc, cache_info)."""
    db = get_db()
    key = params.key()
    doc = db.analyses.find_one({"key": key}, {"_id": 0})
    info = {"analysis": "hit", "weather": "skipped"}
    if not doc:
        with _lock_for(key):  # avoid duplicate upstream calls for concurrent identical requests
            doc = db.analyses.find_one({"key": key}, {"_id": 0})
            if not doc:
                weather, wstatus = ingest.get_weather(params.region, params.start_year, params.end_year)
                computed = compute_analysis(params, weather)
                db.analyses.replace_one({"key": key}, computed, upsert=True)
                doc = db.analyses.find_one({"key": key}, {"_id": 0})
                info = {"analysis": "miss", "weather": wstatus}
    doc.pop("created_at", None)
    doc["region"]["name"] = params.name  # label is display-only and not part of the cache key
    return doc, info