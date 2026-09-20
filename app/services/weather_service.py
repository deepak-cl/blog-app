from __future__ import annotations

import logging
import time
from collections import defaultdict

import httpx

from app.config import (
    CACHE_TTL,
    DEFAULT_WEATHER_LOCATION,
    NWS_USER_AGENT,
    WEATHER_API_URL,
    WEATHER_LATITUDE,
    WEATHER_LONGITUDE,
)
from app.utils.geo import is_us_coordinates, nws_points_url
from app.db.database import (
    get_connection,
    get_latest_cache_entry,
    is_cache_valid,
    save_cache_entry,
)
from app.utils.http_client import get_json
from app.utils.rate_limit import mark_upstream_fetch, should_skip_upstream

logger = logging.getLogger(__name__)

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

NWS_HEADERS = {"User-Agent": NWS_USER_AGENT, "Accept": "application/geo+json"}


class UpstreamRateLimitedError(Exception):
    def __init__(self, source: str, detail: str):
        self.source = source
        super().__init__(detail)


def _fahrenheit_to_celsius(value: float) -> float:
    return round((value - 32) * 5 / 9, 1)


def _nws_quantity(value_obj: dict | None) -> float | None:
    if not value_obj:
        return None
    raw = value_obj.get("value")
    if raw is None:
        return None
    return round(float(raw), 1)


def _aggregate_nws_forecast(periods: list[dict]) -> dict:
    daily: dict[str, dict[str, float | None]] = defaultdict(
        lambda: {"max_f": None, "min_f": None}
    )
    for period in periods:
        date = period["startTime"][:10]
        temp = period["temperature"]
        if period.get("isDaytime"):
            current_max = daily[date]["max_f"]
            daily[date]["max_f"] = temp if current_max is None else max(current_max, temp)
        else:
            current_min = daily[date]["min_f"]
            daily[date]["min_f"] = temp if current_min is None else min(current_min, temp)

    dates = sorted(daily.keys())[:7]
    max_c: list[float | None] = []
    min_c: list[float | None] = []
    precip: list[float | None] = []
    for date in dates:
        entry = daily[date]
        max_c.append(
            _fahrenheit_to_celsius(entry["max_f"]) if entry["max_f"] is not None else None
        )
        min_c.append(
            _fahrenheit_to_celsius(entry["min_f"]) if entry["min_f"] is not None else None
        )
        precip.append(None)

    return {
        "dates": dates,
        "temperature_max_c": max_c,
        "temperature_min_c": min_c,
        "precipitation_mm": precip,
    }


class WeatherService:
    source = "weather"

    async def fetch_remote(self) -> dict:
        payload = await get_json(WEATHER_API_URL)
        current = payload.get("current", {})
        daily = payload.get("daily", {})
        weather_code = current.get("weather_code")

        return {
            "location": DEFAULT_WEATHER_LOCATION,
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
            "upstream": "open-meteo",
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

    async def fetch_remote_nws(self) -> dict:
        points = await get_json(
            nws_points_url(WEATHER_LATITUDE, WEATHER_LONGITUDE),
            headers=NWS_HEADERS,
            retries=2,
        )
        properties = points.get("properties", {})
        forecast_url = properties.get("forecast")
        stations_url = properties.get("observationStations")
        if not forecast_url or not stations_url:
            raise ValueError("NWS points response missing forecast or observation station URLs")

        forecast_payload = await get_json(forecast_url, headers=NWS_HEADERS, retries=2)
        periods = forecast_payload.get("properties", {}).get("periods", [])
        if not periods:
            raise ValueError("NWS forecast returned no periods")

        stations_payload = await get_json(stations_url, headers=NWS_HEADERS, retries=2)
        station_features = stations_payload.get("features", [])
        if not station_features:
            raise ValueError("NWS returned no observation stations")

        station_id = station_features[0]["id"]
        observation = await get_json(
            f"{station_id}/observations/latest",
            headers=NWS_HEADERS,
            retries=2,
        )
        obs_props = observation.get("properties", {})

        return {
            "location": DEFAULT_WEATHER_LOCATION,
            "latitude": WEATHER_LATITUDE,
            "longitude": WEATHER_LONGITUDE,
            "upstream": "nws",
            "current": {
                "temperature_c": _nws_quantity(obs_props.get("temperature")),
                "humidity_percent": _nws_quantity(obs_props.get("relativeHumidity")),
                "wind_speed_kmh": _nws_quantity(obs_props.get("windSpeed")),
                "weather_code": None,
                "condition": obs_props.get("textDescription") or periods[0].get("shortForecast"),
                "observed_at": obs_props.get("timestamp"),
            },
            "forecast_7d": _aggregate_nws_forecast(periods),
        }

    def _stale_response(self, cached: dict) -> dict:
        return {
            **cached,
            "from_cache": True,
            "stale": True,
            "upstream_rate_limited": True,
        }

    async def _try_nws_fallback(self, open_meteo_error: Exception) -> dict:
        if not is_us_coordinates(WEATHER_LATITUDE, WEATHER_LONGITUDE):
            logger.warning(
                "Open-Meteo failed (%s); NWS fallback skipped (non-US coordinates)",
                open_meteo_error,
            )
            if (
                isinstance(open_meteo_error, httpx.HTTPStatusError)
                and open_meteo_error.response.status_code == 429
            ):
                raise UpstreamRateLimitedError(
                    self.source,
                    "Open-Meteo rate limit reached. NWS fallback is US-only; "
                    "retry later or use cached data when available.",
                ) from open_meteo_error
            raise open_meteo_error

        logger.warning(
            "Open-Meteo failed (%s); trying NWS fallback for US coordinates",
            open_meteo_error,
        )
        try:
            return await self.fetch_remote_nws()
        except Exception as nws_error:
            logger.exception("NWS weather fallback failed")
            if (
                isinstance(open_meteo_error, httpx.HTTPStatusError)
                and open_meteo_error.response.status_code == 429
            ):
                raise UpstreamRateLimitedError(
                    self.source,
                    "Open-Meteo rate limit reached and NWS fallback failed. "
                    "Retry later or use cached data when available.",
                ) from nws_error
            raise open_meteo_error from nws_error

    async def get_or_refresh(self, force: bool = False) -> dict:
        with get_connection() as conn:
            cached = get_latest_cache_entry(conn, self.source)
            if not force and is_cache_valid(cached):
                return {
                    **cached,
                    "from_cache": True,
                }

            if should_skip_upstream(self.source, force=force, has_cache=cached is not None):
                logger.info("Skipping weather upstream fetch (min interval); serving cache")
                return self._stale_response(cached)

        start = time.monotonic()
        data: dict | None = None
        open_meteo_error: Exception | None = None

        try:
            data = await self.fetch_remote()
            mark_upstream_fetch(self.source)
        except httpx.HTTPStatusError as exc:
            open_meteo_error = exc
            if exc.response.status_code == 429 and cached is not None:
                logger.warning("Open-Meteo rate limited; returning stale weather cache")
                return self._stale_response(cached)
        except httpx.HTTPError as exc:
            open_meteo_error = exc

        if data is None and open_meteo_error is not None and cached is None:
            data = await self._try_nws_fallback(open_meteo_error)
            mark_upstream_fetch(self.source)
        elif data is None and open_meteo_error is not None:
            if (
                isinstance(open_meteo_error, httpx.HTTPStatusError)
                and open_meteo_error.response.status_code == 429
            ):
                raise UpstreamRateLimitedError(
                    self.source,
                    "Open-Meteo rate limit reached. Cached data served when available; "
                    "retry later or increase refresh interval.",
                ) from open_meteo_error
            raise open_meteo_error

        fetch_duration_ms = int((time.monotonic() - start) * 1000)

        with get_connection() as conn:
            return save_cache_entry(
                conn,
                self.source,
                data,
                CACHE_TTL[self.source],
                fetch_duration_ms=fetch_duration_ms,
            )

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
