from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.db.database import init_db
from app.routers import analytics, health, iss, trivia, weather

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("personal_api_hub")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting Personal API Hub")
    init_db()
    yield
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


@app.get("/")
def root():
    return {
        "name": "Personal API Hub",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "trivia": "/trivia",
            "iss": "/iss",
            "weather": "/weather",
            "analytics": "/analytics/summary",
        },
    }
