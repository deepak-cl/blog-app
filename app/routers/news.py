from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.news_service import NewsService

router = APIRouter(prefix="/news", tags=["news"])
service = NewsService()


@router.get("")
async def get_news(refresh: bool = False):
    """Return world news headlines, using cache unless refresh=true."""
    return await service.get_or_refresh(force=refresh)


@router.post("/refresh")
async def refresh_news():
    """Force refresh world news from RSS feeds."""
    return await service.get_or_refresh(force=True)


@router.get("/cached")
def get_cached_news():
    """Return the latest cached news payload."""
    cached = service.get_cached()
    if cached is None:
        raise HTTPException(status_code=404, detail="No news data cached yet")
    return cached
