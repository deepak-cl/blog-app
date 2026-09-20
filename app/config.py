from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "data" / "hub.db"

# Cache TTL in seconds
CACHE_TTL = {
    "trivia": 3600,
    "iss": 300,
    "weather": 3600,
}

# External API endpoints
TRIVIA_API_URL = "https://opentdb.com/api.php?amount=10&type=multiple"
ISS_API_URL = "https://api.wheretheiss.at/v1/satellites/25544"
ISS_API_URL_FALLBACK = "http://api.open-notify.org/iss-now.json"
WEATHER_API_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=40.7128&longitude=-74.0060"
    "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
    "&timezone=America/New_York&forecast_days=7"
)

# NWS fallback when Open-Meteo is rate-limited (common on shared Render IPs)
NWS_POINTS_URL = "https://api.weather.gov/points/40.7128,-74.0060"
NWS_USER_AGENT = "PersonalAPIHub/1.0 (https://github.com/deepak-cl/blog-app)"

DEFAULT_WEATHER_LOCATION = "New York City"
WEATHER_LATITUDE = 40.7128
WEATHER_LONGITUDE = -74.0060

# ISS proximity reference (default NYC)
ISS_REFERENCE_LAT = 40.7128
ISS_REFERENCE_LNG = -74.0060
ISS_NEAR_THRESHOLD_KM = 2000.0

# Background scheduler (disabled during pytest)
SCHEDULER_ENABLED = os.environ.get("TESTING") != "1"
SSE_HEARTBEAT_SECONDS = 30
