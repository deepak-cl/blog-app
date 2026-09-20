# Geo-based Weather/ISS & Observability

## Geo flow (dashboard → backend)

1. **On dashboard load** (`static/app.js`), the browser shows a short banner explaining why location is requested, then calls `navigator.geolocation.getCurrentPosition`.
2. **If coords are inside India** (lat `6.5–35.5`, lng `68–97.5`):
   - Frontend stores lat/lng and label (`Your location (lat, lng)`).
   - Requests include `?lat=&lng=` on `/analytics/daily-brief`, `/weather/refresh`, `/iss/refresh`, and `/analytics/ai-brief`.
3. **If geolocation is denied or fails**: defaults to Anekal config (`12.7081, 77.6953`) with a persistent notice banner.
4. **If outside India**: modal blocks weather/ISS; no fetch; empty state on weather/ISS cards. Headlines and trivia still load.

## Backend validation

- `app/utils/geo.py` — `is_india_coordinates`, `require_india_coordinates`, `OutsideIndiaError`
- `app/utils/geo_params.py` — FastAPI helper `optional_india_coords(lat, lng)`
- Global handler in `app/main.py` → HTTP **403**:
  ```json
  { "error": "outside_india", "message": "Geographic location is not covered..." }
  ```

## Endpoints with optional `lat` / `lng`

| Endpoint | Behavior |
|----------|----------|
| `GET/POST /weather` | Builds Open-Meteo/wttr URLs from coords; cache keyed by ~0.05° proximity |
| `GET/POST /iss` | ISS position global; adds `distance_km` + `reference_point` when coords provided |
| `GET /analytics/daily-brief` | Prefetches weather for coords; ISS distance uses reference lat/lng |
| `GET/POST /analytics/ai-brief` | Same geo context as daily-brief for AI prompt |

Default scheduler refresh still uses Anekal coords from `app/config.py`.

## Dashboard UI cleanup

Removed from `static/index.html` header: API Docs, API Index, Health links. Backend routes unchanged (`/docs`, `/api`, `/health`).

## Metrics (`GET /metrics`)

Lightweight Prometheus text format (`app/metrics.py` + `app/routers/metrics.py`):

- `http_requests_total{method,path,status}`
- `cache_hits_total{source}` / `cache_misses_total{source}` (weather instrumented)
- `cache_last_fetch_timestamp_seconds{source}` (from SQLite)
- `cache_ttl_seconds{source}`
- `hub_health_status` (1 = DB reachable)

Not linked from dashboard; intended for admin scraping only.

## Tests added

- `test_outside_india_weather_rejected`, `test_outside_india_iss_rejected`
- `test_india_bounds_validation`
- `test_weather_with_custom_india_coords`
- `test_iss_with_custom_reference_coords`
- `test_daily_brief_with_custom_coords`
- `test_metrics_endpoint`
