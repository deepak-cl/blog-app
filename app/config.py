from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "data" / "hub.db"

# Cache TTL in seconds
CACHE_TTL = {
    "trivia": 3600,
    "iss": 300,
    # Longer TTL reduces Open-Meteo pressure on shared Render IPs.
    "weather": 7200,
}

# External API endpoints
TRIVIA_API_URL = "https://opentdb.com/api.php?amount=10&type=multiple"
ISS_API_URL = "https://api.wheretheiss.at/v1/satellites/25544"
ISS_API_URL_FALLBACK = "http://api.open-notify.org/iss-now.json"
WEATHER_LATITUDE = 12.7081
WEATHER_LONGITUDE = 77.6953
WEATHER_TIMEZONE = "Asia/Kolkata"

WEATHER_API_URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={WEATHER_LATITUDE}&longitude={WEATHER_LONGITUDE}"
    "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
    f"&timezone={WEATHER_TIMEZONE}&forecast_days=7"
)

# NWS fallback (US coordinates only) when Open-Meteo is rate-limited
NWS_USER_AGENT = "PersonalAPIHub/1.0 (https://github.com/deepak-cl/blog-app)"

DEFAULT_WEATHER_LOCATION = "Anekal, Bengaluru, Karnataka, India"

# Optional weather providers (see internal/weather-india-fix.md)
IMD_API_KEY = os.environ.get("IMD_API_KEY", "").strip()
IMD_CITY_ID = os.environ.get("IMD_CITY_ID", "42182").strip() or "42182"
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "").strip()

# ISS proximity reference (default: Anekal, Bengaluru)
ISS_REFERENCE_LAT = WEATHER_LATITUDE
ISS_REFERENCE_LNG = WEATHER_LONGITUDE
ISS_REFERENCE_LABEL = "Anekal, Bengaluru (default)"
ISS_NEAR_THRESHOLD_KM = 2000.0

# Background scheduler (disabled during pytest)
SCHEDULER_ENABLED = os.environ.get("TESTING") != "1"
SSE_HEARTBEAT_SECONDS = 30
