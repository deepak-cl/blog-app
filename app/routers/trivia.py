from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.trivia_service import TriviaService

router = APIRouter(prefix="/trivia", tags=["trivia"])
service = TriviaService()


@router.get("")
async def get_trivia(refresh: bool = False):
    """Return trivia questions, using cache unless refresh=true."""
    return await service.get_or_refresh(force=refresh)


@router.post("/refresh")
async def refresh_trivia():
    """Force refresh trivia from Open Trivia DB."""
    return await service.get_or_refresh(force=True)


@router.get("/cached")
def get_cached_trivia():
    """Return the latest cached trivia payload."""
    cached = service.get_cached()
    if cached is None:
        raise HTTPException(status_code=404, detail="No trivia data cached yet")
    return cached
