"""HTTP API. Every analysis endpoint validates input, is rate limited, and serves data read back from MongoDB."""
import hashlib
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from . import db as dbmod
from .config import latest_complete_year, settings
from .db import get_db
from .schemas import AnalysisParams, build_region
from .security import general_limiter, geocode_limiter, heavy_limiter, rate_limit
from .services import analysis as analysis_service
from .services import exports, openmeteo
from .services.trends import METRICS
from .utils import clean_label, slug

router = APIRouter(dependencies=[Depends(rate_limit(general_limiter, "general"))])
heavy = Depends(rate_limit(heavy_limiter, "heavy"))
CACHE_HDR = {"Cache-Control": "public, max-age=300"}


def analysis_params(
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    south: Optional[float] = Query(None, ge=-90, le=90),
    west: Optional[float] = Query(None, ge=-180, le=180),
    north: Optional[float] = Query(None, ge=-90, le=90),
    east: Optional[float] = Query(None, ge=-180, le=180),
    start_year: int = Query(1990, ge=settings.min_year),
    end_year: int = Query(2020),
    percentile: float = Query(95.0, ge=80.0, le=99.5),
    min_days: int = Query(3, ge=2, le=10),
    method: Literal["fixed", "calendar"] = Query("fixed"),
    hazard: Literal["heatwave"] = Query("heatwave"),
    name: Optional[str] = Query(None, max_length=80),
) -> AnalysisParams:
    try:
        region = build_region(lat, lon, south, west, north, east)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    max_y = latest_complete_year()
    if end_year > max_y:
        raise HTTPException(status_code=422, detail=f"end_year cannot be later than {max_y} (the last complete year).")
    if end_year - start_year + 1 < settings.min_span_years:
        raise HTTPException(status_code=422, detail=f"Choose a range of at least {settings.min_span_years} years.")
    return AnalysisParams(region, start_year, end_year, percentile, min_days, method, hazard, clean_label(name))


@router.get("/health")
def health():
    get_db()
    return {"status": "ok", "database": dbmod.db_mode, "time": datetime.now(timezone.utc).isoformat(timespec="seconds")}


@router.get("/meta")
def meta():
    return {
        "min_year": settings.min_year,
        "max_year": latest_complete_year(),
        "min_span_years": settings.min_span_years,
        "max_box_span_deg": settings.max_box_span_deg,
        "hazards": [
            {"id": "heatwave", "label": "Heatwave", "available": True},
        ],
        "metrics": [{"id": k, **v} for k, v in METRICS.items()],
    }


@router.get("/geocode", dependencies=[Depends(rate_limit(geocode_limiter, "geocode"))])
def geocode(q: str = Query(..., min_length=2, max_length=80)):
    q = clean_label(q, fallback="")
    if len(q) < 2:
        raise HTTPException(status_code=422, detail="Search text is too short.")
    key = hashlib.sha256(q.lower().encode()).hexdigest()[:32]
    db = get_db()
    hit = db.geocode_cache.find_one({"key": key}, {"_id": 0})
    if hit:
        return JSONResponse({"results": hit["results"]}, headers=CACHE_HDR)
    results = openmeteo.geocode(q)
    db.geocode_cache.replace_one({"key": key}, {"key": key, "q": q.lower(), "results": results, "created_at": datetime.now(timezone.utc)}, upsert=True)
    return JSONResponse({"results": results}, headers=CACHE_HDR)


@router.get("/analysis", dependencies=[heavy])
def analysis(request: Request, params: AnalysisParams = Depends(analysis_params)):
    doc, cache = analysis_service.get_analysis(params)
    etag = '"%s-%s"' % (doc["key"], doc["meta"]["computed_at"])
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, **CACHE_HDR})
    return JSONResponse({**doc, "cache": cache}, headers={"ETag": etag, **CACHE_HDR})


def _filename(params: AnalysisParams, suffix: str) -> str:
    return f"heatwave_{slug(params.name)}_{params.start_year}-{params.end_year}{suffix}"


@router.get("/analysis/export.csv", dependencies=[heavy])
def export_csv(kind: Literal["yearly", "events"] = "yearly", params: AnalysisParams = Depends(analysis_params)):
    doc, _ = analysis_service.get_analysis(params)
    text = exports.yearly_csv(doc) if kind == "yearly" else exports.events_csv(doc)
    return Response(text, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{_filename(params, "_" + kind + ".csv")}"', **CACHE_HDR})


@router.get("/analysis/export.pdf", dependencies=[heavy])
def export_pdf(params: AnalysisParams = Depends(analysis_params)):
    doc, _ = analysis_service.get_analysis(params)
    return Response(exports.render_pdf(doc), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{_filename(params, ".pdf")}"', **CACHE_HDR})


@router.get("/analysis/plot.png", dependencies=[heavy])
def plot_png(metric: Literal["heatwave_days", "events", "max_duration", "mean_intensity"] = "heatwave_days",
             theme: Literal["dark", "light"] = "dark", params: AnalysisParams = Depends(analysis_params)):
    doc, _ = analysis_service.get_analysis(params)
    return Response(exports.render_plot(doc, metric, theme), media_type="image/png", headers=CACHE_HDR)