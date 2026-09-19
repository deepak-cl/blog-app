# Personal API & Data Hub

A FastAPI application that aggregates data from three external APIs, caches responses in SQLite, and exposes custom analytics endpoints.

## Data Sources

| Source | API | Cache TTL |
|--------|-----|-----------|
| Trivia | [Open Trivia DB](https://opentdb.com/) | 1 hour |
| ISS location | [Open Notify ISS](http://open-notify.org/Open-Notify-API/ISS-Location-Now/) | 5 minutes |
| Weather | [Open-Meteo](https://open-meteo.com/) (NYC) | 30 minutes |

## Setup

```bash
cd personal-api-hub
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

## Endpoints

### Health

- `GET /health` — Service status, database connectivity, cache stats

### Data sources

Each source supports:

- `GET /{source}` — Return cached data or fetch if expired (`?refresh=true` forces fetch)
- `POST /{source}/refresh` — Force refresh from external API
- `GET /{source}/cached` — Return latest cached payload only

Sources: `/trivia`, `/iss`, `/weather`

### Analytics

- `GET /analytics/summary` — Cross-source cache stats and entry counts
- `GET /analytics/trivia` — Difficulty, category, and type breakdown
- `GET /analytics/iss` — Position history and estimated distance traveled (km)
- `GET /analytics/weather` — 7-day forecast trends, warmest/coldest/wettest days

## Project Structure

```
personal-api-hub/
├── app/
│   ├── main.py           # FastAPI app entrypoint
│   ├── config.py         # URLs, TTLs, paths
│   ├── db/               # SQLite layer
│   ├── routers/          # HTTP routes
│   ├── services/         # External API + cache logic
│   └── utils/            # Geo helpers (ISS distance)
├── tests/
├── data/                 # SQLite database (created at runtime)
├── requirements.txt
└── README.md
```

## Testing

```bash
pytest tests/ -v
```

Tests hit live external APIs to verify fetch and caching behavior.

## Example

```bash
# Fetch all sources
curl http://localhost:8000/trivia?refresh=true
curl http://localhost:8000/iss/refresh -X POST
curl http://localhost:8000/weather/refresh -X POST

# Analytics
curl http://localhost:8000/analytics/summary
curl http://localhost:8000/analytics/iss
```
