import os
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
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
from app.utils import rate_limit  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    if TEST_DB.exists():
        TEST_DB.unlink()
    init_db()
    rate_limit._last_upstream_fetch.clear()
    yield
    if TEST_DB.exists():
        TEST_DB.unlink()
    rate_limit._last_upstream_fetch.clear()


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
    assert data.get("upstream") in {"open-meteo", "nws"}

    trends = await client.get("/analytics/weather")
    assert trends.status_code == 200
    assert "daily_forecast" in trends.json()


@pytest.mark.asyncio
async def test_weather_nws_fallback_when_open_meteo_fails(client, monkeypatch):
    from app.services.weather_service import WeatherService

    nws_payload = {
        "location": "Anekal, Bengaluru, Karnataka, India",
        "latitude": 12.7081,
        "longitude": 77.6953,
        "upstream": "nws",
        "current": {
            "temperature_c": 17.2,
            "humidity_percent": 81.0,
            "wind_speed_kmh": 5.4,
            "weather_code": None,
            "condition": "Cloudy",
            "observed_at": "2026-09-20T08:51:00+00:00",
        },
        "forecast_7d": {
            "dates": ["2026-09-20", "2026-09-21"],
            "temperature_max_c": [20.6, 18.3],
            "temperature_min_c": [17.2, 15.0],
            "precipitation_mm": [None, None],
        },
    }

    async def fail_open_meteo(_self):
        request = httpx.Request("GET", "https://api.open-meteo.com/v1/forecast")
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    monkeypatch.setattr(WeatherService, "fetch_remote", fail_open_meteo)
    monkeypatch.setattr(
        WeatherService,
        "fetch_remote_nws",
        AsyncMock(return_value=nws_payload),
    )
    monkeypatch.setattr(
        "app.services.weather_service.is_us_coordinates",
        lambda _lat, _lng: True,
    )

    response = await client.post("/weather/refresh")
    assert response.status_code == 200
    body = response.json()
    assert body["from_cache"] is False
    assert body["data"]["upstream"] == "nws"
    assert body["data"]["current"]["condition"] == "Cloudy"


@pytest.mark.asyncio
async def test_weather_skips_nws_outside_us_when_open_meteo_fails(client, monkeypatch):
    from app.services.weather_service import WeatherService

    async def fail_open_meteo(_self):
        request = httpx.Request("GET", "https://api.open-meteo.com/v1/forecast")
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    monkeypatch.setattr(WeatherService, "fetch_remote", fail_open_meteo)
    monkeypatch.setattr(
        "app.services.weather_service.is_us_coordinates",
        lambda _lat, _lng: False,
    )

    response = await client.post("/weather/refresh")
    assert response.status_code == 429
    body = response.json()
    assert "NWS fallback is US-only" in body["detail"]


@pytest.mark.asyncio
async def test_analytics_summary(client):
    trivia = await client.post("/trivia/refresh")
    iss = await client.post("/iss/refresh")
    weather = await client.post("/weather/refresh")
    assert trivia.status_code == 200
    assert iss.status_code == 200
    assert weather.status_code == 200

    response = await client.get("/analytics/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_cache_entries"] >= 3
    assert "trivia" in body["sources"]

    trivia = await client.get("/analytics/trivia")
    assert trivia.status_code == 200
    assert "by_difficulty" in trivia.json()


@pytest.mark.asyncio
async def test_daily_brief(client):
    await client.post("/trivia/refresh")
    await client.post("/iss/refresh")
    await client.post("/weather/refresh")

    response = await client.get("/analytics/daily-brief")
    assert response.status_code == 200
    body = response.json()
    assert "generated_at" in body
    assert body["weather"] is not None
    assert body["weather"]["location"] == "Anekal, Bengaluru, Karnataka, India"
    assert body["iss"] is not None
    assert "distance_km" in body["iss"]
    assert body["iss"]["reference_point"]["label"] == "Anekal, Bengaluru (default)"
    assert "near_reference" in body["iss"]
    assert body["trivia"] is not None
    assert "question" in body["trivia"]
    assert "correct_answer" not in body["trivia"]


@pytest.mark.asyncio
async def test_cache_efficiency(client):
    await client.post("/weather/refresh")

    response = await client.get("/analytics/cache-efficiency")
    assert response.status_code == 200
    body = response.json()
    assert "sources" in body
    assert "summary" in body

    weather = next(row for row in body["sources"] if row["source"] == "weather")
    assert weather["entry_count"] >= 1
    assert weather["ttl_seconds"] == 3600
    assert weather["hit_friendly_status"] in {
        "hit_friendly",
        "stale_serves_fallback",
        "cold_miss",
    }


@pytest.mark.asyncio
async def test_api_index(client):
    response = await client.get("/api")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Personal API Hub"
    assert "daily_brief" in body["endpoints"]
