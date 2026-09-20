from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import httpx

from app.config import (
    CACHE_TTL,
    DEFAULT_WEATHER_LOCATION,
    IMD_CITY_ID,
    NWS_USER_AGENT,
    OPENWEATHER_API_KEY,
    WEATHER_LATITUDE,
    WEATHER_LONGITUDE,
    WEATHER_TIMEZONE,
)
from app.db.database import (
    get_connection,
    get_latest_cache_entry,
    is_cache_valid,
    save_cache_entry,
)
from app.metrics import record_cache_hit, record_cache_miss
from app.utils.geo import (
    is_india_coordinates,
    is_us_coordinates,
    nws_points_url,
    open_meteo_forecast_url,
    wttr_json_url,
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
WTTR_HEADERS = {"User-Agent": "PersonalAPIHub/1.0 (https://github.com/deepak-cl/blog-app)"}
OPEN_METEO_RETRIES = 5


class UpstreamRateLimitedError(Exception):
    def __init__(self, source: str, detail: str):
        self.source = source
        super().__init__(detail)


def _imd_api_key() -> str:
    return os.environ.get("IMD_API_KEY", "").strip()


def _openweather_api_key() -> str:
    return os.environ.get("OPENWEATHER_API_KEY", "").strip() or OPENWEATHER_API_KEY


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


def _parse_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return round(float(str(value).strip()), 1)
    except (TypeError, ValueError):
        return None


def _imd_record(payload: object) -> dict:
    if isinstance(payload, list) and payload:
        record = payload[0]
    elif isinstance(payload, dict):
        record = payload.get("data", payload)
        if isinstance(record, list) and record:
            record = record[0]
    else:
        raise ValueError("IMD response was empty")
    if not isinstance(record, dict):
        raise ValueError("IMD response format was unexpected")
    return record


def _imd_forecast_days(record: dict) -> tuple[list[str], list[float | None], list[float | None], list[str]]:
    base_date = record.get("Date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        start = datetime.strptime(str(base_date)[:10], "%Y-%m-%d")
    except ValueError:
        start = datetime.now(timezone.utc)

    day_specs = [
        ("Todays_Forecast_Max_Temp", "Todays_Forecast_Min_temp", "Todays_Forecast"),
    ]
    for day_num in range(2, 8):
        day_specs.append(
            (f"Day_{day_num}_Max_Temp", f"Day_{day_num}_Min_temp", f"Day_{day_num}_Forecast")
        )

    dates: list[str] = []
    max_temps: list[float | None] = []
    min_temps: list[float | None] = []
    conditions: list[str] = []
    for offset, (max_key, min_key, forecast_key) in enumerate(day_specs):
        day = start + timedelta(days=offset)
        dates.append(day.strftime("%Y-%m-%d"))
        max_temps.append(_parse_float(record.get(max_key)))
        min_temps.append(_parse_float(record.get(min_key)))
        conditions.append(str(record.get(forecast_key) or "Unknown").strip() or "Unknown")
    return dates, max_temps, min_temps, conditions


class WeatherService:
    source = "weather"

    def __init__(
        self,
        *,
        latitude: float | None = None,
        longitude: float | None = None,
        location_label: str | None = None,
    ) -> None:
        self._latitude = latitude if latitude is not None else WEATHER_LATITUDE
        self._longitude = longitude if longitude is not None else WEATHER_LONGITUDE
        self._location_label = location_label

    def _weather_payload(
        self,
        *,
        upstream: str,
        current: dict,
        forecast_7d: dict,
        latitude: float | None = None,
        longitude: float | None = None,
        location: str | None = None,
    ) -> dict:
        return {
            "location": location or self._location_label or DEFAULT_WEATHER_LOCATION,
            "latitude": latitude if latitude is not None else self._latitude,
            "longitude": longitude if longitude is not None else self._longitude,
            "upstream": upstream,
            "current": current,
            "forecast_7d": forecast_7d,
        }

    async def fetch_remote(self) -> dict:
        url = open_meteo_forecast_url(
            self._latitude,
            self._longitude,
            timezone=WEATHER_TIMEZONE,
        )
        payload = await get_json(url, retries=OPEN_METEO_RETRIES)
        current = payload.get("current", {})
        daily = payload.get("daily", {})
        weather_code = current.get("weather_code")

        return self._weather_payload(
            upstream="open-meteo",
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
            current={
                "temperature_c": current.get("temperature_2m"),
                "humidity_percent": current.get("relative_humidity_2m"),
                "wind_speed_kmh": current.get("wind_speed_10m"),
                "weather_code": weather_code,
                "condition": WEATHER_CODE_LABELS.get(weather_code, "Unknown"),
                "observed_at": current.get("time"),
            },
            forecast_7d={
                "dates": daily.get("time", []),
                "temperature_max_c": daily.get("temperature_2m_max", []),
                "temperature_min_c": daily.get("temperature_2m_min", []),
                "precipitation_mm": daily.get("precipitation_sum", []),
            },
        )

    async def fetch_remote_imd(self) -> dict:
        api_key = _imd_api_key()
        if not api_key:
            raise ValueError("IMD_API_KEY is not configured")

        headers = {"X-API-Key": api_key}
        urls = [
            (
                "https://api.imd.gov.in/api/v1/cityforecastloc"
                f"?lat={self._latitude}&lon={self._longitude}"
            ),
            f"https://api.imd.gov.in/api/v1/cityforecastloc?id={IMD_CITY_ID}",
            f"https://api.imd.gov.in/api/v1/cityforecast?id={IMD_CITY_ID}",
        ]

        last_error: Exception | None = None
        record: dict | None = None
        for url in urls:
            try:
                payload = await get_json(url, headers=headers, retries=2)
                record = _imd_record(payload)
                break
            except Exception as exc:
                last_error = exc
                logger.warning("IMD fetch failed url=%s error=%s", url, exc)

        if record is None:
            raise last_error or ValueError("IMD returned no forecast data")

        dates, max_temps, min_temps, conditions = _imd_forecast_days(record)
        station_name = str(record.get("Station_Name") or "").strip()
        location = station_name or DEFAULT_WEATHER_LOCATION

        return self._weather_payload(
            upstream="imd",
            location=location,
            latitude=_parse_float(record.get("Latitude")) or self._latitude,
            longitude=_parse_float(record.get("Longitude")) or self._longitude,
            current={
                "temperature_c": _parse_float(record.get("Today_Max_temp"))
                or _parse_float(record.get("Todays_Forecast_Max_Temp")),
                "humidity_percent": _parse_float(record.get("Relative_Humidity_at_1730")),
                "wind_speed_kmh": None,
                "weather_code": None,
                "condition": conditions[0] if conditions else "Unknown",
                "observed_at": str(record.get("Date") or ""),
            },
            forecast_7d={
                "dates": dates,
                "temperature_max_c": max_temps,
                "temperature_min_c": min_temps,
                "precipitation_mm": [_parse_float(record.get("Past_24_hrs_Rainfall"))] + [None] * (len(dates) - 1),
            },
        )

    async def fetch_remote_openweather(self) -> dict:
        api_key = _openweather_api_key()
        if not api_key:
            raise ValueError("OPENWEATHER_API_KEY is not configured")

        current_url = (
            "https://api.openweathermap.org/data/2.5/weather"
            f"?lat={self._latitude}&lon={self._longitude}&appid={api_key}&units=metric"
        )
        forecast_url = (
            "https://api.openweathermap.org/data/2.5/forecast"
            f"?lat={self._latitude}&lon={self._longitude}&appid={api_key}&units=metric"
        )

        current_payload = await get_json(current_url, retries=2)
        forecast_payload = await get_json(forecast_url, retries=2)

        daily: dict[str, dict[str, float | None]] = defaultdict(
            lambda: {"max_c": None, "min_c": None, "precip_mm": 0.0}
        )
        for entry in forecast_payload.get("list", []):
            dt_txt = entry.get("dt_txt", "")
            if not dt_txt:
                continue
            date = dt_txt[:10]
            main = entry.get("main", {})
            temp = main.get("temp")
            if temp is None:
                continue
            temp = round(float(temp), 1)
            bucket = daily[date]
            bucket["max_c"] = temp if bucket["max_c"] is None else max(bucket["max_c"], temp)
            bucket["min_c"] = temp if bucket["min_c"] is None else min(bucket["min_c"], temp)
            rain = entry.get("rain", {}).get("3h") or 0.0
            bucket["precip_mm"] = round(float(bucket["precip_mm"]) + float(rain), 1)

        dates = sorted(daily.keys())[:7]
        weather_block = current_payload.get("weather", [{}])
        condition = weather_block[0].get("description", "Unknown") if weather_block else "Unknown"

        return self._weather_payload(
            upstream="openweather",
            current={
                "temperature_c": round(float(current_payload.get("main", {}).get("temp", 0)), 1),
                "humidity_percent": current_payload.get("main", {}).get("humidity"),
                "wind_speed_kmh": round(float(current_payload.get("wind", {}).get("speed", 0)) * 3.6, 1),
                "weather_code": weather_block[0].get("id") if weather_block else None,
                "condition": condition.title(),
                "observed_at": datetime.fromtimestamp(
                    current_payload.get("dt", 0), tz=timezone.utc
                ).isoformat(),
            },
            forecast_7d={
                "dates": dates,
                "temperature_max_c": [daily[d]["max_c"] for d in dates],
                "temperature_min_c": [daily[d]["min_c"] for d in dates],
                "precipitation_mm": [daily[d]["precip_mm"] for d in dates],
            },
        )

    async def fetch_remote_wttr(self) -> dict:
        url = wttr_json_url(self._latitude, self._longitude)
        payload = await get_json(url, headers=WTTR_HEADERS, retries=2)

        current = (payload.get("current_condition") or [{}])[0]
        condition = ((current.get("weatherDesc") or [{}])[0]).get("value", "Unknown")
        nearest = (payload.get("nearest_area") or [{}])[0]
        area_name = ((nearest.get("areaName") or [{}])[0]).get("value")
        region = ((nearest.get("region") or [{}])[0]).get("value")
        country = ((nearest.get("country") or [{}])[0]).get("value")
        location_bits = [bit for bit in (area_name, region, country) if bit]
        location = ", ".join(location_bits) if location_bits else DEFAULT_WEATHER_LOCATION

        weather_days = payload.get("weather", [])[:7]
        dates: list[str] = []
        max_temps: list[float | None] = []
        min_temps: list[float | None] = []
        precip: list[float | None] = []
        for day in weather_days:
            dates.append(day.get("date", ""))
            max_temps.append(_parse_float(day.get("maxtempC")))
            min_temps.append(_parse_float(day.get("mintempC")))
            precip.append(_parse_float(day.get("totalSnow_cm")))

        return self._weather_payload(
            upstream="wttr",
            location=location,
            latitude=_parse_float(nearest.get("latitude")) or self._latitude,
            longitude=_parse_float(nearest.get("longitude")) or self._longitude,
            current={
                "temperature_c": _parse_float(current.get("temp_C")),
                "humidity_percent": _parse_float(current.get("humidity")),
                "wind_speed_kmh": _parse_float(current.get("windspeedKmph")),
                "weather_code": current.get("weatherCode"),
                "condition": condition,
                "observed_at": current.get("observation_time"),
            },
            forecast_7d={
                "dates": dates,
                "temperature_max_c": max_temps,
                "temperature_min_c": min_temps,
                "precipitation_mm": precip,
            },
        )

    async def fetch_remote_nws(self) -> dict:
        points = await get_json(
            nws_points_url(self._latitude, self._longitude),
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

        return self._weather_payload(
            upstream="nws",
            current={
                "temperature_c": _nws_quantity(obs_props.get("temperature")),
                "humidity_percent": _nws_quantity(obs_props.get("relativeHumidity")),
                "wind_speed_kmh": _nws_quantity(obs_props.get("windSpeed")),
                "weather_code": None,
                "condition": obs_props.get("textDescription") or periods[0].get("shortForecast"),
                "observed_at": obs_props.get("timestamp"),
            },
            forecast_7d=_aggregate_nws_forecast(periods),
        )

    def _stale_response(self, cached: dict) -> dict:
        return {
            **cached,
            "from_cache": True,
            "stale": True,
            "upstream_rate_limited": True,
        }

    def _provider_chain(self) -> list[tuple[str, str]]:
        chain: list[tuple[str, str]] = [("open-meteo", "fetch_remote")]

        if _imd_api_key() and is_india_coordinates(self._latitude, self._longitude):
            chain.append(("imd", "fetch_remote_imd"))

        if _openweather_api_key():
            chain.append(("openweather", "fetch_remote_openweather"))

        if is_us_coordinates(self._latitude, self._longitude):
            chain.append(("nws", "fetch_remote_nws"))

        chain.append(("wttr", "fetch_remote_wttr"))
        return chain

    async def _fetch_with_fallbacks(self, cached: dict | None) -> dict:
        errors: list[str] = []
        open_meteo_rate_limited = False

        for provider_name, method_name in self._provider_chain():
            fetch_method = getattr(self, method_name)
            try:
                data = await fetch_method()
                logger.info("Weather fetched from upstream=%s", provider_name)
                return data
            except httpx.HTTPStatusError as exc:
                if provider_name == "open-meteo" and exc.response.status_code == 429:
                    open_meteo_rate_limited = True
                errors.append(f"{provider_name}: HTTP {exc.response.status_code}")
                logger.warning("Weather provider %s failed: %s", provider_name, exc)
            except Exception as exc:
                errors.append(f"{provider_name}: {exc}")
                logger.warning("Weather provider %s failed: %s", provider_name, exc)

        if cached is not None:
            logger.warning("All weather providers failed; serving stale cache")
            return self._stale_response(cached)

        detail = "All weather providers failed. " + "; ".join(errors[:4])
        if open_meteo_rate_limited:
            raise UpstreamRateLimitedError(
                self.source,
                detail
                + ". Open-Meteo limits requests per IP on shared hosts. "
                "Set IMD_API_KEY or OPENWEATHER_API_KEY for reliable Bengaluru weather.",
            )
        raise UpstreamRateLimitedError(self.source, detail)

    def _cache_matches_coords(self, cached: dict | None) -> bool:
        if cached is None:
            return False
        data = cached.get("data") or {}
        cached_lat = data.get("latitude")
        cached_lng = data.get("longitude")
        if cached_lat is None or cached_lng is None:
            return True
        return (
            abs(float(cached_lat) - self._latitude) < 0.05
            and abs(float(cached_lng) - self._longitude) < 0.05
        )

    async def get_or_refresh(self, force: bool = False) -> dict:
        with get_connection() as conn:
            cached = get_latest_cache_entry(conn, self.source)
            cache_ok = self._cache_matches_coords(cached)
            if not force and cache_ok and is_cache_valid(cached):
                record_cache_hit(self.source)
                return {
                    **cached,
                    "from_cache": True,
                }

            if (
                cache_ok
                and should_skip_upstream(self.source, force=force, has_cache=cached is not None)
            ):
                logger.info("Skipping weather upstream fetch (min interval); serving cache")
                record_cache_hit(self.source)
                return self._stale_response(cached)

        record_cache_miss(self.source)
        start = time.monotonic()
        data = await self._fetch_with_fallbacks(cached if cache_ok else None)
        mark_upstream_fetch(self.source)

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
