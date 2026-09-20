import os
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Use an isolated test database
TEST_DB = Path(__file__).resolve().parent / "test_hub.db"
os.environ["TESTING"] = "1"

# Patch database path before importing app modules
import app.config as config

config.DATABASE_PATH = TEST_DB

from app.db.database import init_db, is_cache_valid  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    if TEST_DB.exists():
        TEST_DB.unlink()
    init_db()
    yield
    if TEST_DB.exists():
        TEST_DB.unlink()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "cache_ttl_seconds" in body


def test_is_cache_valid_accepts_naive_expiry():
    future = "2099-01-01T00:00:00"
    assert is_cache_valid({"expires_at": future}) is True


@pytest.mark.asyncio
async def test_trivia_fetch_and_cache(client):
    first = await client.get("/trivia?refresh=true")
    assert first.status_code == 200
    data = first.json()
    assert data["from_cache"] is False
    assert data["data"]["question_count"] == 10

    second = await client.get("/trivia")
    assert second.status_code == 200
    cached = second.json()
    assert cached["from_cache"] is True

    cached_only = await client.get("/trivia/cached")
    assert cached_only.status_code == 200


@pytest.mark.asyncio
async def test_iss_fetch_and_history(client):
    first = await client.post("/iss/refresh")
    assert first.status_code == 200
    assert "latitude" in first.json()["data"]

    second = await client.post("/iss/refresh")
    assert second.status_code == 200

    analytics = await client.get("/analytics/iss")
    assert analytics.status_code == 200
    body = analytics.json()
    assert body["sample_count"] >= 2
    assert body["distance_traveled_km"] >= 0


@pytest.mark.asyncio
async def test_weather_fetch_and_analytics(client):
    response = await client.post("/weather/refresh")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "current" in data
    assert "forecast_7d" in data

    trends = await client.get("/analytics/weather")
    assert trends.status_code == 200
    assert "daily_forecast" in trends.json()


@pytest.mark.asyncio
async def test_analytics_summary(client):
    await client.post("/trivia/refresh")
    await client.post("/iss/refresh")
    await client.post("/weather/refresh")

    response = await client.get("/analytics/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_cache_entries"] >= 3
    assert "trivia" in body["sources"]

    trivia = await client.get("/analytics/trivia")
    assert trivia.status_code == 200
    assert "by_difficulty" in trivia.json()
