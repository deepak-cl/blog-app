from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.services.ai_brief_service import AIBriefNotConfiguredError, AIBriefService
from app.services.weather_service import WeatherService
from app.utils.errors import friendly_http_error
from app.services.analytics_service import AnalyticsService
from app.services.reverse_geocode_service import resolve_place_label
from app.utils.geo_params import optional_india_coords

router = APIRouter(prefix="/analytics", tags=["analytics"])
service = AnalyticsService()
ai_brief_service = AIBriefService()


@router.get("/summary")
def analytics_summary():
    """Cross-source summary stats."""
    return service.summary()


@router.get("/trivia")
def trivia_analytics():
    """Difficulty and category breakdown for cached trivia."""
    return service.trivia_breakdown()


@router.get("/iss")
def iss_analytics(limit: int = 50):
    """ISS position history and estimated distance traveled."""
    return service.iss_history(limit=limit)


@router.get("/weather")
def weather_analytics():
    """7-day weather trends and comparisons."""
    return service.weather_trends()


@router.get("/daily-brief")
async def daily_brief(
    lat: float | None = None,
    lng: float | None = None,
    reference_lat: float | None = None,
    reference_lng: float | None = None,
    near_threshold_km: float | None = None,
):
    """Cross-source daily brief: weather, ISS proximity, and a trivia question."""
    coords = optional_india_coords(lat, lng)
    kwargs: dict = {}
    if coords is not None:
        ref_lat, ref_lng = coords
        kwargs["reference_lat"] = ref_lat
        kwargs["reference_lng"] = ref_lng
        place_label = await resolve_place_label(ref_lat, ref_lng)
        kwargs["reference_label"] = place_label
        weather_service = WeatherService(
            latitude=ref_lat,
            longitude=ref_lng,
            location_label=place_label,
        )
        await weather_service.get_or_refresh(force=False)
    else:
        if reference_lat is not None:
            kwargs["reference_lat"] = reference_lat
        if reference_lng is not None:
            kwargs["reference_lng"] = reference_lng
    if near_threshold_km is not None:
        kwargs["near_threshold_km"] = near_threshold_km
    return service.daily_brief(**kwargs)


@router.get("/cache-efficiency")
def cache_efficiency():
    """Per-source cache efficiency and hit-friendly status."""
    return service.cache_efficiency()


@router.get("/news-brief")
def news_brief(limit: int = 5):
    """Top headlines from world news, AI developments, and entertainment."""
    return service.news_brief(limit=limit)


@router.get("/ai-brief/providers")
def ai_brief_providers():
    """List AI providers that have API keys configured on the server."""
    return {"providers": ai_brief_service.configured_providers()}


@router.get("/ai-brief")
async def ai_brief_get(
    provider: str | None = Query(default=None),
    lat: float | None = None,
    lng: float | None = None,
):
    """Generate a short AI daily brief from cached hub data."""
    return await _generate_ai_brief(provider, lat=lat, lng=lng)


@router.post("/ai-brief")
async def ai_brief_post(
    provider: str | None = Query(default=None),
    lat: float | None = None,
    lng: float | None = None,
):
    """Generate a short AI daily brief from cached hub data."""
    return await _generate_ai_brief(provider, lat=lat, lng=lng)


async def _generate_ai_brief(
    provider: str | None,
    *,
    lat: float | None = None,
    lng: float | None = None,
) -> dict:
    coords = optional_india_coords(lat, lng)
    try:
        return await ai_brief_service.generate(provider=provider, coords=coords)
    except AIBriefNotConfiguredError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
            headers={"X-AI-Brief-Status": "not-configured"},
        ) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raise HTTPException(
            status_code=502 if status >= 500 else status,
            detail=friendly_http_error(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=friendly_http_error(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
