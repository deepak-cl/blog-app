from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.iss_service import ISSService

router = APIRouter(prefix="/iss", tags=["iss"])
service = ISSService()


@router.get("")
async def get_iss(refresh: bool = False):
    """Return current ISS position, using cache unless refresh=true."""
    return await service.get_or_refresh(force=refresh)


@router.post("/refresh")
async def refresh_iss():
    """Force refresh ISS position from Open Notify."""
    return await service.get_or_refresh(force=True)


@router.get("/cached")
def get_cached_iss():
    """Return the latest cached ISS position."""
    cached = service.get_cached()
    if cached is None:
        raise HTTPException(status_code=404, detail="No ISS data cached yet")
    return cached
