from __future__ import annotations

from fastapi import APIRouter

from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])
service = AnalyticsService()


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
