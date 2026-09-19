from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

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
