from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.db.database import init_db
from app.routers import analytics, health, iss, trivia, weather


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


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
