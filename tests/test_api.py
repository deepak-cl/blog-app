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
    assert data.get("upstream") in {"open-meteo", "nws", "imd", "openweather", "wttr"}

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
async def test_weather_wttr_fallback_when_open_meteo_fails(client, monkeypatch):
    from app.services.weather_service import WeatherService

    wttr_payload = {
        "location": "Anekal, Bengaluru, Karnataka, India",
        "latitude": 12.7081,
        "longitude": 77.6953,
        "upstream": "wttr",
        "current": {
            "temperature_c": 24.0,
            "humidity_percent": 77.0,
            "wind_speed_kmh": 11.0,
            "weather_code": "176",
            "condition": "Patchy rain nearby",
            "observed_at": "09:55 AM",
        },
        "forecast_7d": {
            "dates": ["2026-09-20", "2026-09-21"],
            "temperature_max_c": [28.0, 27.0],
            "temperature_min_c": [20.0, 19.0],
            "precipitation_mm": [0.0, 0.0],
        },
    }

    async def fail_open_meteo(_self):
        request = httpx.Request("GET", "https://api.open-meteo.com/v1/forecast")
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    monkeypatch.setattr(WeatherService, "fetch_remote", fail_open_meteo)
    monkeypatch.setattr(
        WeatherService,
        "fetch_remote_wttr",
        AsyncMock(return_value=wttr_payload),
    )
    monkeypatch.delenv("IMD_API_KEY", raising=False)
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)

    response = await client.post("/weather/refresh")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["upstream"] == "wttr"
    assert body["data"]["current"]["condition"] == "Patchy rain nearby"


@pytest.mark.asyncio
async def test_weather_openweather_fallback(client, monkeypatch):
    from app.services.weather_service import WeatherService

    openweather_payload = {
        "location": "Anekal, Bengaluru, Karnataka, India",
        "latitude": 12.7081,
        "longitude": 77.6953,
        "upstream": "openweather",
        "current": {
            "temperature_c": 25.0,
            "humidity_percent": 70,
            "wind_speed_kmh": 12.0,
            "weather_code": 801,
            "condition": "Few Clouds",
            "observed_at": "2026-09-20T10:00:00+00:00",
        },
        "forecast_7d": {
            "dates": ["2026-09-20"],
            "temperature_max_c": [28.0],
            "temperature_min_c": [20.0],
            "precipitation_mm": [0.0],
        },
    }

    async def fail_open_meteo(_self):
        raise httpx.HTTPStatusError(
            "rate limited",
            request=httpx.Request("GET", "https://api.open-meteo.com/v1/forecast"),
            response=httpx.Response(429, request=httpx.Request("GET", "https://api.open-meteo.com/v1/forecast")),
        )

    monkeypatch.setattr(WeatherService, "fetch_remote", fail_open_meteo)
    monkeypatch.setattr(
        WeatherService,
        "fetch_remote_openweather",
        AsyncMock(return_value=openweather_payload),
    )
    monkeypatch.setenv("OPENWEATHER_API_KEY", "test-openweather-key")
    monkeypatch.delenv("IMD_API_KEY", raising=False)

    response = await client.post("/weather/refresh")
    assert response.status_code == 200
    assert response.json()["data"]["upstream"] == "openweather"


@pytest.mark.asyncio
async def test_weather_imd_fallback(client, monkeypatch):
    from app.services.weather_service import WeatherService

    imd_payload = {
        "location": "Bengaluru",
        "latitude": 12.97,
        "longitude": 77.59,
        "upstream": "imd",
        "current": {
            "temperature_c": 29.0,
            "humidity_percent": 65.0,
            "wind_speed_kmh": None,
            "weather_code": None,
            "condition": "Partly cloudy sky",
            "observed_at": "2026-09-20",
        },
        "forecast_7d": {
            "dates": ["2026-09-20", "2026-09-21"],
            "temperature_max_c": [29.0, 28.0],
            "temperature_min_c": [20.0, 19.0],
            "precipitation_mm": [0.0, None],
        },
    }

    async def fail_open_meteo(_self):
        raise httpx.HTTPStatusError(
            "rate limited",
            request=httpx.Request("GET", "https://api.open-meteo.com/v1/forecast"),
            response=httpx.Response(429, request=httpx.Request("GET", "https://api.open-meteo.com/v1/forecast")),
        )

    monkeypatch.setattr(WeatherService, "fetch_remote", fail_open_meteo)
    monkeypatch.setattr(
        WeatherService,
        "fetch_remote_imd",
        AsyncMock(return_value=imd_payload),
    )
    monkeypatch.setenv("IMD_API_KEY", "test-imd-key")

    response = await client.post("/weather/refresh")
    assert response.status_code == 200
    assert response.json()["data"]["upstream"] == "imd"


@pytest.mark.asyncio
async def test_weather_all_providers_fail_returns_429(client, monkeypatch):
    from app.services.weather_service import WeatherService

    async def fail(_self):
        raise httpx.HTTPStatusError(
            "rate limited",
            request=httpx.Request("GET", "https://api.open-meteo.com/v1/forecast"),
            response=httpx.Response(429, request=httpx.Request("GET", "https://api.open-meteo.com/v1/forecast")),
        )

    for method in (
        "fetch_remote",
        "fetch_remote_imd",
        "fetch_remote_openweather",
        "fetch_remote_wttr",
    ):
        monkeypatch.setattr(WeatherService, method, fail)
    monkeypatch.delenv("IMD_API_KEY", raising=False)
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)

    response = await client.post("/weather/refresh")
    assert response.status_code == 429
    body = response.json()
    assert "All weather providers failed" in body["detail"]


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
    assert weather["ttl_seconds"] == 7200
    assert weather["hit_friendly_status"] in {
        "hit_friendly",
        "stale_serves_fallback",
        "cold_miss",
    }


def test_anthropic_model_id_is_current():
    from app.services.ai_brief_service import PROVIDER_CONFIG

    assert PROVIDER_CONFIG["anthropic"]["model"] == "claude-haiku-4-5"


def test_friendly_http_error_messages():
    from app.utils.errors import friendly_http_status_error

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(404, request=request)
    exc = httpx.HTTPStatusError("not found", request=request, response=response)
    message = friendly_http_status_error(exc)
    assert "Anthropic" in message
    assert "model" in message.lower()


@pytest.mark.asyncio
async def test_ai_brief_providers_empty(client, monkeypatch):
    for env_var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)

    response = await client.get("/analytics/ai-brief/providers")
    assert response.status_code == 200
    assert response.json()["providers"] == []


@pytest.mark.asyncio
async def test_ai_brief_no_key_configured(client, monkeypatch):
    for env_var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)

    response = await client.post("/analytics/ai-brief")
    assert response.status_code == 503
    body = response.json()
    assert "No AI provider API keys configured" in body["detail"]


@pytest.mark.asyncio
async def test_ai_brief_missing_provider_key(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    response = await client.post("/analytics/ai-brief?provider=anthropic")
    assert response.status_code == 503
    assert "anthropic" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_index(client):
    response = await client.get("/api")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Personal API Hub"
    assert "daily_brief" in body["endpoints"]
    assert "ai_brief" in body["endpoints"]
