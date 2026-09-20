from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.ai_dev_service import AiDevService

router = APIRouter(prefix="/ai-dev", tags=["ai-dev"])
service = AiDevService()


@router.get("")
async def get_ai_dev(refresh: bool = False):
    """Return AI development headlines, using cache unless refresh=true."""
    return await service.get_or_refresh(force=refresh)


@router.post("/refresh")
async def refresh_ai_dev():
    """Force refresh AI developments from RSS feeds."""
    return await service.get_or_refresh(force=True)


@router.get("/cached")
def get_cached_ai_dev():
    """Return the latest cached AI developments payload."""
    cached = service.get_cached()
    if cached is None:
        raise HTTPException(status_code=404, detail="No AI developments cached yet")
    return cached
