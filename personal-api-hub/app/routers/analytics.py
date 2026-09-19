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
