from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.services.ai_brief_service import AIBriefNotConfiguredError, AIBriefService
from app.utils.errors import friendly_http_error
from app.services.analytics_service import AnalyticsService

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
def daily_brief(
    reference_lat: float | None = None,
    reference_lng: float | None = None,
    near_threshold_km: float | None = None,
):
    """Cross-source daily brief: weather, ISS proximity, and a trivia question."""
    kwargs: dict = {}
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


@router.get("/ai-brief/providers")
def ai_brief_providers():
    """List AI providers that have API keys configured on the server."""
    return {"providers": ai_brief_service.configured_providers()}


@router.get("/ai-brief")
async def ai_brief_get(provider: str | None = Query(default=None)):
    """Generate a short AI daily brief from cached hub data."""
    return await _generate_ai_brief(provider)


@router.post("/ai-brief")
async def ai_brief_post(provider: str | None = Query(default=None)):
    """Generate a short AI daily brief from cached hub data."""
    return await _generate_ai_brief(provider)


async def _generate_ai_brief(provider: str | None) -> dict:
    try:
        return await ai_brief_service.generate(provider=provider)
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
