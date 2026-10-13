"""Central, environment-driven configuration."""
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Bump when detection / trend logic changes: it is part of every cache key,
# so old cached analyses are never served after a logic change.
ALGO_VERSION = 3  # 3: analyses now carry the robustness grid | 2: single homogeneous reanalysis model (see HISTORICAL_MODEL)


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


class Settings:
    mongo_uri: str = os.getenv("MONGO_URI", "").strip()
    mongo_db: str = os.getenv("MONGO_DB", "climate_hazards")
    cors_origins = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if o.strip()
    ]
    rate_limit_general: int = _int("RATE_LIMIT_GENERAL_PER_MIN", 120)
    rate_limit_heavy: int = _int("RATE_LIMIT_HEAVY_PER_MIN", 20)
    rate_limit_geocode: int = _int("RATE_LIMIT_GEOCODE_PER_MIN", 30)
    trust_proxy: bool = os.getenv("TRUST_PROXY", "0") == "1"
    weather_cache_days: int = _int("WEATHER_CACHE_DAYS", 30)
    analysis_cache_days: int = _int("ANALYSIS_CACHE_DAYS", 30)
    geocode_cache_days: int = 7

    # Open-Meteo's default 'best match' silently switches to a different model (IFS, 9 km) from 2017,
    # which creates a fake step change. A trend study must use ONE homogeneous reanalysis for all years.
    historical_model: str = os.getenv("HISTORICAL_MODEL", "era5_land").strip().lower()

    # Input limits
    min_year: int = 1950
    min_span_years: int = 10
    max_box_span_deg: float = 10.0
    min_box_span_deg: float = 0.1

    static_dir: Path = Path(
        os.getenv("STATIC_DIR", str(Path(__file__).resolve().parents[2] / "frontend" / "dist"))
    )


settings = Settings()
if settings.historical_model not in {"era5_land", "era5"}:
    settings.historical_model = "era5_land"

MODEL_LABEL = {"era5_land": "ERA5-Land reanalysis, 0.1 deg", "era5": "ERA5 reanalysis, 0.25 deg"}


def latest_complete_year() -> int:
    """The archive lags real time by a few days, so only full past years are offered."""
    return date.today().year - 1