from __future__ import annotations

import math

# India's approximate bounding box (mainland + islands)
INDIA_LAT_MIN = 6.5
INDIA_LAT_MAX = 35.5
INDIA_LNG_MIN = 68.0
INDIA_LNG_MAX = 97.5

OUTSIDE_INDIA_MESSAGE = (
    "Geographic location is not covered. This service currently supports "
    "locations within India only."
)


class OutsideIndiaError(Exception):
    """Raised when coordinates fall outside India's supported bounding box."""

    def __init__(self, lat: float, lng: float):
        self.lat = lat
        self.lng = lng
        super().__init__(OUTSIDE_INDIA_MESSAGE)


def is_india_coordinates(lat: float, lng: float) -> bool:
    """True when lat/lng fall within India's approximate bounding box."""
    return (
        INDIA_LAT_MIN <= lat <= INDIA_LAT_MAX
        and INDIA_LNG_MIN <= lng <= INDIA_LNG_MAX
    )


def require_india_coordinates(lat: float, lng: float) -> None:
    """Raise OutsideIndiaError when coordinates are outside India."""
    if not is_india_coordinates(lat, lng):
        raise OutsideIndiaError(lat, lng)


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


def open_meteo_forecast_url(
    lat: float,
    lng: float,
    *,
    timezone: str = "Asia/Kolkata",
    forecast_days: int = 7,
) -> str:
    return (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lng}"
        "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&timezone={timezone}&forecast_days={forecast_days}"
    )


def wttr_json_url(lat: float, lng: float) -> str:
    return f"https://wttr.in/{lat},{lng}?format=j1"


def format_coords_label(lat: float, lng: float) -> str:
    return f"Your location ({lat:.2f}°, {lng:.2f}°)"


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
