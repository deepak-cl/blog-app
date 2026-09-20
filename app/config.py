from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "data" / "hub.db"

# Cache TTL in seconds
CACHE_TTL = {
    "trivia": 3600,
    "iss": 300,
    "weather": 1800,
}

# External API endpoints
TRIVIA_API_URL = "https://opentdb.com/api.php?amount=10&type=multiple"
ISS_API_URL = "http://api.open-notify.org/iss-now.json"
WEATHER_API_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=40.7128&longitude=-74.0060"
    "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
    "&timezone=America/New_York&forecast_days=7"
)

DEFAULT_WEATHER_LOCATION = "New York City"
