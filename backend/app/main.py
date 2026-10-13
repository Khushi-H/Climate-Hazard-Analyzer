"""FastAPI entrypoint. Run with:  uvicorn app.main:app --reload --port 8000"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pymongo.errors import PyMongoError

from .config import settings
from .db import get_db
from .routes import router
from .security import SECURITY_HEADERS
from .services.hazards import InsufficientDataError
from .services.openmeteo import UpstreamError

log = logging.getLogger("heatline")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        get_db()
    except Exception as exc:  # surfaced per-request as a 503 instead of crashing the boot
        log.error("Database init failed: %s", exc)
    yield


app = FastAPI(title="Heatline Climate Hazard API", version="1.0.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET"], allow_headers=["*"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    return response


@app.exception_handler(UpstreamError)
async def upstream_handler(request: Request, exc: UpstreamError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(InsufficientDataError)
async def insufficient_handler(request: Request, exc: InsufficientDataError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(PyMongoError)
async def mongo_handler(request: Request, exc: PyMongoError):
    log.error("MongoDB error: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "The database is temporarily unavailable."})


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server."})


app.include_router(router, prefix="/api")

# Optional: serve the built React app from the same service (single-URL deployment).
_static = settings.static_dir
if (_static / "index.html").is_file():
    if (_static / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (_static / full_path).resolve()
        if full_path and candidate.is_file() and _static.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_static / "index.html")
