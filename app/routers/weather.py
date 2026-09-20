from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.weather_service import WeatherService
from app.services.reverse_geocode_service import resolve_place_label
from app.utils.geo_params import optional_india_coords

router = APIRouter(prefix="/weather", tags=["weather"])


async def _weather_service(
    coords: tuple[float, float] | None,
) -> WeatherService:
    if coords is None:
        return WeatherService()
    lat, lng = coords
    location_label = await resolve_place_label(lat, lng)
    return WeatherService(
        latitude=lat,
        longitude=lng,
        location_label=location_label,
    )


@router.get("")
async def get_weather(
    refresh: bool = False,
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
):
    """Return weather for Anekal/Bengaluru or optional India lat/lng."""
    coords = optional_india_coords(lat, lng)
    service = await _weather_service(coords)
    return await service.get_or_refresh(force=refresh)


@router.post("/refresh")
async def refresh_weather(
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
):
    """Force refresh weather (Open-Meteo primary; fallback chain when needed)."""
    coords = optional_india_coords(lat, lng)
    service = await _weather_service(coords)
    return await service.get_or_refresh(force=True)


@router.get("/cached")
async def get_cached_weather(
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
):
    """Return the latest cached weather payload."""
    coords = optional_india_coords(lat, lng)
    service = await _weather_service(coords)
    cached = service.get_cached()
    if cached is None:
        raise HTTPException(status_code=404, detail="No weather data cached yet")
    if coords is not None and not service._cache_matches_coords(cached):
        raise HTTPException(
            status_code=404,
            detail="No weather data cached for the requested coordinates.",
        )
    return cached
