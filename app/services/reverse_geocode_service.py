from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.config import WEATHER_LATITUDE, WEATHER_LONGITUDE
from app.utils.geo import haversine_km, require_india_coordinates

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 3600
OPEN_METEO_REVERSE_URL = "https://geocoding-api.open-meteo.com/v1/reverse"
BIGDATACLOUD_REVERSE_URL = "https://api.bigdatacloud.net/data/reverse-geocode-client"

NEAR_BENGALURU_KM = 80.0
FALLBACK_NEAR_LABEL = "Near Bengaluru"

_memory_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def clear_reverse_geocode_cache() -> None:
    """Clear in-memory reverse geocode cache (used in tests)."""
    _memory_cache.clear()


def _cache_key(lat: float, lng: float) -> str:
    return f"{lat:.2f},{lng:.2f}"


def fallback_coords_label(lat: float, lng: float) -> str:
    """Fallback label when upstream reverse geocoding is unavailable."""
    distance = haversine_km(lat, lng, WEATHER_LATITUDE, WEATHER_LONGITUDE)
    if distance <= NEAR_BENGALURU_KM:
        return FALLBACK_NEAR_LABEL
    return f"{lat:.2f}°, {lng:.2f}°"


def _build_label(city: str | None, state: str | None, country: str | None) -> str:
    parts = [part for part in (city, state, country) if part]
    return ", ".join(parts) if parts else FALLBACK_NEAR_LABEL


class ReverseGeocodeService:
    def _get_cached(self, lat: float, lng: float) -> dict[str, Any] | None:
        key = _cache_key(lat, lng)
        entry = _memory_cache.get(key)
        if entry is None:
            return None
        expires_at, payload = entry
        if time.time() > expires_at:
            _memory_cache.pop(key, None)
            return None
        return payload

    def _set_cached(self, lat: float, lng: float, payload: dict[str, Any]) -> None:
        _memory_cache[_cache_key(lat, lng)] = (time.time() + CACHE_TTL_SECONDS, payload)

    async def lookup(self, lat: float, lng: float) -> dict[str, Any]:
        require_india_coordinates(lat, lng)

        cached = self._get_cached(lat, lng)
        if cached is not None:
            return {**cached, "from_cache": True}

        try:
            payload = await self._fetch_open_meteo(lat, lng)
        except Exception as exc:
            logger.warning("Open-Meteo reverse geocode failed for %s,%s: %s", lat, lng, exc)
            try:
                payload = await self._fetch_bigdatacloud(lat, lng)
            except Exception as exc2:
                logger.warning("BigDataCloud reverse geocode failed for %s,%s: %s", lat, lng, exc2)
                payload = {
                    "label": fallback_coords_label(lat, lng),
                    "city": None,
                    "state": None,
                    "country": "India",
                    "provider": "fallback",
                }

        self._set_cached(lat, lng, payload)
        return {**payload, "from_cache": False}

    async def _fetch_open_meteo(self, lat: float, lng: float) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                OPEN_METEO_REVERSE_URL,
                params={
                    "latitude": lat,
                    "longitude": lng,
                    "language": "en",
                    "count": 1,
                },
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("results") or []
        if not results:
            raise ValueError("No reverse geocode results from Open-Meteo")

        place = results[0]
        country = place.get("country") or ""
        country_code = (place.get("country_code") or "").upper()
        if country_code != "IN" and "india" not in country.lower():
            raise ValueError(f"Reverse geocode returned non-India location: {country}")

        city = place.get("name")
        state = place.get("admin1")
        return {
            "label": _build_label(city, state, country or "India"),
            "city": city,
            "state": state,
            "country": country or "India",
            "provider": "open-meteo",
        }

    async def _fetch_bigdatacloud(self, lat: float, lng: float) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                BIGDATACLOUD_REVERSE_URL,
                params={
                    "latitude": lat,
                    "longitude": lng,
                    "localityLanguage": "en",
                },
            )
            response.raise_for_status()
            data = response.json()

        country = data.get("countryName") or ""
        country_code = (data.get("countryCode") or "").upper()
        if country_code != "IN" and "india" not in country.lower():
            raise ValueError(f"Reverse geocode returned non-India location: {country}")

        city = data.get("city") or data.get("locality") or data.get("localityInfo", {}).get("administrative", [{}])[0].get("name")
        state = data.get("principalSubdivision")
        return {
            "label": _build_label(city, state, country or "India"),
            "city": city,
            "state": state,
            "country": country or "India",
            "provider": "bigdatacloud",
        }


async def resolve_place_label(lat: float, lng: float) -> str:
    """Resolve a human-readable place label for India coordinates."""
    result = await ReverseGeocodeService().lookup(lat, lng)
    return result["label"]
