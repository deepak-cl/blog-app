from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import ISS_NEAR_THRESHOLD_KM, ISS_REFERENCE_LABEL, ISS_REFERENCE_LAT, ISS_REFERENCE_LNG
from app.services.iss_service import ISSService
from app.utils.geo import format_coords_label, haversine_km
from app.utils.geo_params import optional_india_coords

router = APIRouter(prefix="/iss", tags=["iss"])
service = ISSService()


def _enrich_with_reference(
    payload: dict,
    *,
    reference_lat: float,
    reference_lng: float,
    reference_label: str,
) -> dict:
    data = payload.get("data") or {}
    if "latitude" not in data or "longitude" not in data:
        return payload

    distance_km = haversine_km(
        float(data["latitude"]),
        float(data["longitude"]),
        reference_lat,
        reference_lng,
    )
    payload = {
        **payload,
        "reference_point": {
            "latitude": reference_lat,
            "longitude": reference_lng,
            "label": reference_label,
        },
        "distance_km": round(distance_km, 2),
        "near_reference": distance_km <= ISS_NEAR_THRESHOLD_KM,
        "near_threshold_km": ISS_NEAR_THRESHOLD_KM,
    }
    return payload


@router.get("")
async def get_iss(
    refresh: bool = False,
    lat: float | None = None,
    lng: float | None = None,
):
    """Return current ISS position; optional lat/lng sets the distance reference point."""
    coords = optional_india_coords(lat, lng)
    result = await service.get_or_refresh(force=refresh)
    if coords is not None:
        ref_lat, ref_lng = coords
        result = _enrich_with_reference(
            result,
            reference_lat=ref_lat,
            reference_lng=ref_lng,
            reference_label=format_coords_label(ref_lat, ref_lng),
        )
    return result


@router.post("/refresh")
async def refresh_iss(
    lat: float | None = None,
    lng: float | None = None,
):
    """Force refresh ISS position from upstream providers."""
    coords = optional_india_coords(lat, lng)
    result = await service.get_or_refresh(force=True)
    if coords is not None:
        ref_lat, ref_lng = coords
        result = _enrich_with_reference(
            result,
            reference_lat=ref_lat,
            reference_lng=ref_lng,
            reference_label=format_coords_label(ref_lat, ref_lng),
        )
    return result


@router.get("/cached")
def get_cached_iss(
    lat: float | None = None,
    lng: float | None = None,
):
    """Return the latest cached ISS position."""
    coords = optional_india_coords(lat, lng)
    cached = service.get_cached()
    if cached is None:
        raise HTTPException(status_code=404, detail="No ISS data cached yet")
    if coords is not None:
        ref_lat, ref_lng = coords
        cached = _enrich_with_reference(
            cached,
            reference_lat=ref_lat,
            reference_lng=ref_lng,
            reference_label=format_coords_label(ref_lat, ref_lng),
        )
    return cached
