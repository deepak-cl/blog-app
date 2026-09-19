from __future__ import annotations

import httpx

from app.config import CACHE_TTL, DEFAULT_WEATHER_LOCATION, WEATHER_API_URL
from app.db.database import (
    get_connection,
    get_latest_cache_entry,
    is_cache_valid,
    save_cache_entry,
)


WEATHER_CODE_LABELS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
}


class WeatherService:
    source = "weather"

    async def fetch_remote(self) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(WEATHER_API_URL)
            response.raise_for_status()
            payload = response.json()

        current = payload.get("current", {})
        daily = payload.get("daily", {})
        weather_code = current.get("weather_code")

        return {
            "location": DEFAULT_WEATHER_LOCATION,
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
            "current": {
                "temperature_c": current.get("temperature_2m"),
                "humidity_percent": current.get("relative_humidity_2m"),
                "wind_speed_kmh": current.get("wind_speed_10m"),
                "weather_code": weather_code,
                "condition": WEATHER_CODE_LABELS.get(weather_code, "Unknown"),
                "observed_at": current.get("time"),
            },
            "forecast_7d": {
                "dates": daily.get("time", []),
                "temperature_max_c": daily.get("temperature_2m_max", []),
                "temperature_min_c": daily.get("temperature_2m_min", []),
                "precipitation_mm": daily.get("precipitation_sum", []),
            },
        }

    async def get_or_refresh(self, force: bool = False) -> dict:
        with get_connection() as conn:
            cached = get_latest_cache_entry(conn, self.source)
            if not force and is_cache_valid(cached):
                return {
                    **cached,
                    "from_cache": True,
                }

            data = await self.fetch_remote()
            return save_cache_entry(conn, self.source, data, CACHE_TTL[self.source])

    def get_cached(self) -> dict | None:
        with get_connection() as conn:
            cached = get_latest_cache_entry(conn, self.source)
            if cached is None:
                return None
            return {
                **cached,
                "from_cache": True,
                "cache_valid": is_cache_valid(cached),
            }
