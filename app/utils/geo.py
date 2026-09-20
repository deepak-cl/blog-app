from __future__ import annotations

import math


def is_india_coordinates(lat: float, lng: float) -> bool:
    """True when lat/lng fall within India's approximate bounding box."""
    return 6.0 <= lat <= 37.0 and 68.0 <= lng <= 97.5


def is_us_coordinates(lat: float, lng: float) -> bool:
    """True when lat/lng fall within US NWS coverage (continental US, AK, HI, PR)."""
    if 24.0 <= lat <= 49.5 and -125.0 <= lng <= -66.0:
        return True
    if 51.0 <= lat <= 72.0 and -180.0 <= lng <= -129.0:
        return True
    if 18.0 <= lat <= 23.0 and -161.0 <= lng <= -154.0:
        return True
    if 17.5 <= lat <= 18.6 and -67.5 <= lng <= -65.0:
        return True
    return False


def nws_points_url(lat: float, lng: float) -> str:
    return f"https://api.weather.gov/points/{lat},{lng}"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points on Earth in kilometers."""
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))
