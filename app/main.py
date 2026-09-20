from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db.database import init_db
from app.metrics import MetricsMiddleware
from app.routers import (
    ai_dev,
    analytics,
    entertainment,
    events,
    geo,
    health,
    iss,
    metrics,
    news,
    trivia,
    weather,
)
from app.services.scheduler import refresh_scheduler
from app.services.weather_service import UpstreamRateLimitedError
from app.utils.errors import friendly_http_error
from app.utils.geo import OUTSIDE_INDIA_MESSAGE, OutsideIndiaError

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
        "Aggregates trivia, ISS location, weather, world news, and AI developments "
        "from external APIs and RSS feeds with SQLite caching and custom analytics."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(MetricsMiddleware)


@app.exception_handler(OutsideIndiaError)
async def outside_india_handler(_: Request, exc: OutsideIndiaError):
    return JSONResponse(
        status_code=403,
        content={
            "error": "outside_india",
            "message": OUTSIDE_INDIA_MESSAGE,
            "latitude": exc.lat,
            "longitude": exc.lng,
        },
    )


@app.exception_handler(UpstreamRateLimitedError)
async def rate_limit_handler(_: Request, exc: UpstreamRateLimitedError):
    return JSONResponse(
        status_code=429,
        content={
            "detail": str(exc),
            "source": exc.source,
            "hint": (
                "Open-Meteo limits requests per IP on shared hosts. Stale cache is served when "
                "available. For Bengaluru, set IMD_API_KEY or OPENWEATHER_API_KEY on Render."
            ),
        },
    )


@app.exception_handler(httpx.HTTPError)
async def upstream_http_error_handler(_: Request, exc: httpx.HTTPError):
    status_code = 502
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        status_code = 429
    return JSONResponse(
        status_code=status_code,
        content={"detail": friendly_http_error(exc)},
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

app.include_router(metrics.router)
app.include_router(geo.router)
app.include_router(health.router)
app.include_router(trivia.router)
app.include_router(iss.router)
app.include_router(weather.router)
app.include_router(news.router)
app.include_router(ai_dev.router)
app.include_router(entertainment.router)
app.include_router(analytics.router)
app.include_router(events.router)


@app.get("/api")
def api_index():
    return {
        "name": "Personal API Hub",
        "docs": "/docs",
        "dashboard": "/",
        "endpoints": {
            "geo_reverse": "/geo/reverse",
            "health": "/health",
            "trivia": "/trivia",
            "iss": "/iss",
            "weather": "/weather",
            "news": "/news",
            "ai_dev": "/ai-dev",
            "entertainment": "/entertainment",
            "analytics": "/analytics/summary",
            "news_brief": "/analytics/news-brief",
            "daily_brief": "/analytics/daily-brief",
            "ai_brief": "/analytics/ai-brief",
            "ai_brief_providers": "/analytics/ai-brief/providers",
            "cache_efficiency": "/analytics/cache-efficiency",
            "metrics": "/metrics",
            "events_stream": "/events/stream",
        },
    }


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
