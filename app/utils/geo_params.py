from __future__ import annotations

from fastapi import HTTPException, Query

from app.utils.geo import require_india_coordinates


def optional_india_coords(
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
) -> tuple[float, float] | None:
    """Parse optional lat/lng query params; validate India bounds when provided."""
    if lat is None and lng is None:
        return None
    if lat is None or lng is None:
        raise HTTPException(
            status_code=400,
            detail="Both lat and lng query parameters are required when specifying a location.",
        )
    require_india_coordinates(lat, lng)
    return lat, lng
