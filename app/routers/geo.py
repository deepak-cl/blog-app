from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.reverse_geocode_service import ReverseGeocodeService
from app.utils.geo import require_india_coordinates

router = APIRouter(prefix="/geo", tags=["geo"])
service = ReverseGeocodeService()


@router.get("/reverse")
async def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
):
    """Reverse geocode India lat/lng to a human-readable place name."""
    require_india_coordinates(lat, lng)
    return await service.lookup(lat, lng)
