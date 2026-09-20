from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.entertainment_service import EntertainmentService

router = APIRouter(prefix="/entertainment", tags=["entertainment"])
service = EntertainmentService()


@router.get("")
async def get_entertainment(refresh: bool = False):
    """Return entertainment headlines, using cache unless refresh=true."""
    return await service.get_or_refresh(force=refresh)


@router.post("/refresh")
async def refresh_entertainment():
    """Force refresh entertainment headlines from RSS feeds."""
    return await service.get_or_refresh(force=True)


@router.get("/cached")
def get_cached_entertainment():
    """Return the latest cached entertainment payload."""
    cached = service.get_cached()
    if cached is None:
        raise HTTPException(status_code=404, detail="No entertainment data cached yet")
    return cached
