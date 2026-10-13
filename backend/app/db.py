"""MongoDB access. Falls back to an in-memory mongomock database when MONGO_URI is empty."""
import logging
import threading

from pymongo import ASCENDING, MongoClient

from .config import settings

log = logging.getLogger("heatline.db")

_lock = threading.Lock()
_db = None
db_mode = "uninitialised"


def _init_indexes(db) -> None:
    day = 24 * 3600
    specs = [
        (db.weather_cache, settings.weather_cache_days * day),
        (db.analyses, settings.analysis_cache_days * day),
        (db.geocode_cache, settings.geocode_cache_days * day),
    ]
    for coll, ttl in specs:
        try:
            coll.create_index([("key", ASCENDING)], unique=True)
            coll.create_index([("created_at", ASCENDING)], expireAfterSeconds=ttl)
        except Exception as exc:  # pragma: no cover - index creation must never block startup
            log.warning("Could not create indexes on %s: %s", coll.name, exc)


def get_db():
    global _db, db_mode
    if _db is not None:
        return _db
    with _lock:
        if _db is not None:
            return _db
        if settings.mongo_uri:
            client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
            db_mode = "mongodb"
        else:
            import mongomock

            client = mongomock.MongoClient()
            db_mode = "in-memory (mongomock)"
            log.warning("MONGO_URI not set: using an in-memory database. Data is lost on restart.")
        _db = client[settings.mongo_db]
        _init_indexes(_db)
        return _db


def reset_for_tests() -> None:
    global _db
    _db = None
