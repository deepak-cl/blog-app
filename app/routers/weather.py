from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.weather_service import WeatherService

router = APIRouter(prefix="/weather", tags=["weather"])
service = WeatherService()


@router.get("")
async def get_weather(refresh: bool = False):
    """Return weather for NYC, using cache unless refresh=true."""
    return await service.get_or_refresh(force=refresh)


@router.post("/refresh")
async def refresh_weather():
    """Force refresh weather (Open-Meteo primary, NWS fallback when needed)."""
    return await service.get_or_refresh(force=True)


@router.get("/cached")
def get_cached_weather():
    """Return the latest cached weather payload."""
    cached = service.get_cached()
    if cached is None:
        raise HTTPException(status_code=404, detail="No weather data cached yet")
    return cached
