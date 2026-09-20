from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db.database import init_db
from app.routers import analytics, events, health, iss, trivia, weather
from app.services.scheduler import refresh_scheduler
from app.services.weather_service import UpstreamRateLimitedError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("personal_api_hub")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting Personal API Hub")
    init_db()
    refresh_scheduler.start()
    yield
    refresh_scheduler.shutdown()
    logger.info("Stopping Personal API Hub")


app = FastAPI(
    title="Personal API Hub",
    description=(
        "Aggregates trivia, ISS location, and weather from external APIs "
        "with SQLite caching and custom analytics."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(UpstreamRateLimitedError)
async def rate_limit_handler(_: Request, exc: UpstreamRateLimitedError):
    return JSONResponse(
        status_code=429,
        content={
            "detail": str(exc),
            "source": exc.source,
            "hint": (
                "Open-Meteo limits requests per IP. Stale cache is served when available; "
                "NWS fallback applies only for US coordinates."
            ),
        },
    )


@app.exception_handler(httpx.HTTPError)
async def upstream_http_error_handler(_: Request, exc: httpx.HTTPError):
    return JSONResponse(
        status_code=502,
        content={"detail": f"Upstream API request failed: {exc}"},
    )


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(
        status_code=502,
        content={"detail": str(exc)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "path": str(request.url.path),
            "hint": "Check the server terminal for a full traceback.",
        },
    )

app.include_router(health.router)
app.include_router(trivia.router)
app.include_router(iss.router)
app.include_router(weather.router)
app.include_router(analytics.router)
app.include_router(events.router)


@app.get("/api")
def api_index():
    return {
        "name": "Personal API Hub",
        "docs": "/docs",
        "dashboard": "/",
        "endpoints": {
            "health": "/health",
            "trivia": "/trivia",
            "iss": "/iss",
            "weather": "/weather",
            "analytics": "/analytics/summary",
            "daily_brief": "/analytics/daily-brief",
            "ai_brief": "/analytics/ai-brief",
            "ai_brief_providers": "/analytics/ai-brief/providers",
            "cache_efficiency": "/analytics/cache-efficiency",
            "events_stream": "/events/stream",
        },
    }


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
