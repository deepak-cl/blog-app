# Personal API & Data Hub

A small **API aggregator** built with **FastAPI** and **SQLite**. It pulls data from three external APIs (trivia, ISS location, and weather), caches the responses locally, and exposes custom analytics endpoints on top of that cached data.

Use it as a personal data hub: fetch fresh data on demand, inspect what is cached, and run analytics without calling upstream APIs every time.

---

## What this project does

| Layer | Purpose |
|-------|---------|
| **Fetch** | Calls Open Trivia DB, Open Notify (ISS), and Open-Meteo |
| **Cache** | Stores each response in SQLite with a per-source TTL |
| **Serve** | REST endpoints to read cached or fresh data |
| **Analyze** | Aggregated stats across trivia, ISS movement, and weather trends |

No API keys are required. All three upstream services are free and public.

---

## Prerequisites

Before you start, make sure you have:

- **Python 3.10+** (`python3 --version`)
- **pip** (usually bundled with Python)
- **Internet access** (the app calls live external APIs)
- **Git** (to clone the repository)

Optional but recommended:

- **[Bruno](https://www.usebruno.com/downloads)** — GUI client for testing endpoints (collection included)
- **curl** — for quick command-line checks

---

## Getting started (new to this project)

Follow these steps if you are setting this up for the first time.

### 1. Clone the repository

```bash
git clone https://github.com/deepak-cl/blog-app.git
cd blog-app
```

### 2. Check out the feature branch

The Personal API Hub lives on its own branch until merged:

```bash
git fetch origin
git checkout cursor/personal-api-data-hub-0354
```

### 3. Create a virtual environment

From the repo root:

```bash
cd personal-api-hub
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Start the server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You should see output like `Uvicorn running on http://0.0.0.0:8000`.

### 6. Verify it works

Open in your browser:

- **Root:** http://localhost:8000/
- **Health:** http://localhost:8000/health
- **Interactive docs:** http://localhost:8000/docs

Or from the terminal:

```bash
curl http://localhost:8000/health
```

If `status` is `"healthy"` and `database.connected` is `true`, you are good to go.

### 7. Populate the cache (recommended first run)

Analytics endpoints need cached data. Refresh all three sources once:

```bash
curl -X POST http://localhost:8000/trivia/refresh
curl -X POST http://localhost:8000/iss/refresh
curl -X POST http://localhost:8000/weather/refresh
```

Then try analytics:

```bash
curl http://localhost:8000/analytics/summary
```

---

## Data sources

| Source | Upstream API | What you get | Cache TTL |
|--------|--------------|--------------|-----------|
| Trivia | [Open Trivia DB](https://opentdb.com/) | 10 multiple-choice questions | 1 hour |
| ISS | [Open Notify ISS Now](http://open-notify.org/Open-Notify-API/ISS-Location-Now/) | Current latitude/longitude | 5 minutes |
| Weather | [Open-Meteo](https://open-meteo.com/) | Current conditions + 7-day NYC forecast | 30 minutes |

The SQLite database is created automatically at `data/hub.db` on first run. You do not need to create tables or run migrations manually.

---

## How caching works

1. **GET `/{source}`** — Returns cached data if still fresh; otherwise fetches from the upstream API and stores the result.
2. **`?refresh=true`** — Forces a fresh fetch on GET (e.g. `GET /trivia?refresh=true`).
3. **POST `/{source}/refresh`** — Always fetches and updates the cache.
4. **GET `/{source}/cached`** — Returns the latest cached payload only; returns `404` if nothing is cached yet.

TTL values are defined in `app/config.py` and reported by `GET /health`.

---

## API reference

### Root & health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Service name and endpoint index |
| `GET` | `/health` | Health check, DB status, cache stats |

### Data sources

Each of `/trivia`, `/iss`, and `/weather` supports:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/{source}` | Cached or auto-fetch (`?refresh=true` to force) |
| `POST` | `/{source}/refresh` | Force refresh from upstream |
| `GET` | `/{source}/cached` | Latest cache entry only |

### Analytics

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/analytics/summary` | Cross-source cache stats and entry counts |
| `GET` | `/analytics/trivia` | Difficulty, category, and question-type breakdown |
| `GET` | `/analytics/iss` | Position history and estimated distance traveled (km) |
| `GET` | `/analytics/weather` | 7-day trends; warmest, coldest, and wettest days |

Full request/response schemas are available at http://localhost:8000/docs when the server is running.

---

## Testing with Bruno

A ready-made [Bruno](https://www.usebruno.com/) collection is included at:

```
personal-api-hub/bruno/Personal API Hub/
```

### Open the collection

1. Install Bruno from https://www.usebruno.com/downloads
2. In Bruno: **Open Collection** → select the folder above
3. Choose the **Local** environment (`baseUrl` = `http://localhost:8000`)
4. Make sure the server is running (see [Getting started](#getting-started-new-to-this-project))

### Suggested test order

1. **Health** → Health Check
2. **Trivia / ISS / Weather** → Refresh (POST) on each source
3. **Analytics** → Summary, then Trivia, ISS, and Weather analytics

The collection includes 18 requests across Root, Health, Trivia, ISS, Weather, and Analytics folders.

---

## Running tests

Automated tests call live external APIs to verify fetch and caching:

```bash
cd personal-api-hub
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v
```

All 5 tests should pass. You need network access for the test run.

---

## Project structure

```
personal-api-hub/
├── app/
│   ├── main.py              # FastAPI app entrypoint
│   ├── config.py            # API URLs, cache TTLs, DB path
│   ├── db/                  # SQLite layer
│   ├── routers/             # HTTP routes (health, trivia, iss, weather, analytics)
│   ├── services/            # External API fetch + cache logic
│   └── utils/               # Geo helpers (ISS distance via Haversine)
├── bruno/
│   └── Personal API Hub/    # Bruno collection (.bru files)
├── tests/                   # pytest suite
├── data/                    # SQLite database (created at runtime)
├── requirements.txt
└── README.md
```

---

## Configuration

Edit `app/config.py` to change:

- **Cache TTLs** — `CACHE_TTL` dict (seconds per source)
- **Upstream URLs** — `TRIVIA_API_URL`, `ISS_API_URL`, `WEATHER_API_URL`
- **Weather location** — coordinates in `WEATHER_API_URL` (default: New York City)

The database path defaults to `data/hub.db` relative to this folder.

---

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| `command not found: uvicorn` | Activate your venv, or run `pip install -r requirements.txt` again |
| `404` on `/trivia/cached` | Call `POST /trivia/refresh` first to populate the cache |
| Empty analytics | Refresh all three sources, then hit `/analytics/summary` |
| External API errors | Check internet connection; upstream services may be temporarily down |
| Port 8000 in use | Start on another port: `uvicorn app.main:app --port 8001` and update Bruno `baseUrl` |

---

## Example curl session

```bash
# Health
curl http://localhost:8000/health

# Fetch and cache all sources
curl http://localhost:8000/trivia?refresh=true
curl -X POST http://localhost:8000/iss/refresh
curl -X POST http://localhost:8000/weather/refresh

# Read from cache only
curl http://localhost:8000/trivia/cached

# Analytics
curl http://localhost:8000/analytics/summary
curl http://localhost:8000/analytics/trivia
curl http://localhost:8000/analytics/iss
curl http://localhost:8000/analytics/weather
```

---

## Tech stack

- **FastAPI** — HTTP API framework
- **SQLite** — Local cache storage
- **httpx** — Async HTTP client for upstream APIs
- **pytest** — Test runner
