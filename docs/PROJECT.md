# Personal API Hub — Project Lookup

> **For AI agents and developers:** Read this file first before making changes.
> **Maintenance rule:** Update this document whenever you add, remove, or change features, endpoints, config, or setup steps.

---

## 1. What this project is

**Personal API Hub** is a FastAPI + SQLite application that:

1. Fetches data from three public external APIs (trivia, ISS location, weather)
2. Caches responses in a local SQLite database with per-source TTL
3. Serves REST endpoints for cached/fresh data
4. Exposes custom analytics endpoints derived from cached data

No API keys required. No external database server required.

**Repository:** https://github.com/deepak-cl/blog-app (planned rename: `personal-api-hub`)
**Active branch:** `cursor/personal-api-data-hub-0354`
**Previous PR:** closed by user; work continues on feature branch

---

## 2. Current feature set (as built)

| Area | Status | Notes |
|------|--------|-------|
| Trivia feed | Done | Open Trivia DB, 10 MCQ, 1h TTL |
| ISS location | Done | Open Notify, 5min TTL, position history |
| Weather feed | Done | Open-Meteo NYC, 30min TTL, 7-day forecast |
| SQLite caching | Done | Auto-created at `data/hub.db`; optional `fetch_duration_ms` |
| Background scheduler | Done | APScheduler refreshes all sources on TTL intervals |
| Analytics | Done | summary, trivia, iss, weather, **daily-brief**, **cache-efficiency** |
| SSE events stream | Done | `GET /events/stream` — health, cache stats, refresh notices |
| Web dashboard | Done | Dark-theme SPA at `/` (`static/`) |
| Health endpoint | Done | Always HTTP 200; check `status` field |
| Deploy config | Done | `Dockerfile`, `render.yaml` (Render free tier) |
| Bruno collection | Done | 22+ requests in `bruno/Personal API Hub/` |
| Python 3.9 support | Done | `from __future__ import annotations` in all app modules |
| Error handling | Done | 502 for upstream failures; 500 logs traceback |
| Legacy Java blog app | Removed | Spring Boot / Maven deleted from repo |

---

## 3. Tech stack

| Layer | Choice |
|-------|--------|
| Language | Python 3.9+ |
| Web framework | FastAPI 0.115 |
| Server | Uvicorn |
| HTTP client | httpx (async) |
| Database | SQLite (file-based) |
| Tests | pytest + pytest-asyncio |
| API testing | Bruno (.bru collection) |

---

## 4. Architecture

```
Client (curl / Bruno / browser)
        |
        v
   FastAPI (app/main.py)
        |
   +----+----+----+
   |    |    |    |
routers services analytics
   |    |    |
   +----+----+
        |
   SQLite (data/hub.db)
        |
   External APIs (trivia, ISS, weather)
```

### Layer responsibilities

| Layer | Path | Role |
|-------|------|------|
| Entry | `app/main.py` | App setup, lifespan, scheduler, static UI mount |
| Config | `app/config.py` | API URLs, cache TTLs, ISS reference point, scheduler |
| Routers | `app/routers/` | HTTP endpoints only; delegate to services |
| Services | `app/services/` | Fetch upstream APIs, cache logic, scheduler, event bus |
| Analytics | `app/services/analytics_service.py` | Aggregations over cached data |
| Database | `app/db/database.py` | SQLite schema, cache CRUD, ISS position history |
| Utils | `app/utils/geo.py` | Haversine distance for ISS analytics |
| Static UI | `static/` | Dashboard HTML/CSS/JS served at `/` |

---

## 5. Directory structure

```
.
├── app/
│   ├── main.py
│   ├── config.py
│   ├── db/database.py
│   ├── routers/          # health, trivia, iss, weather, analytics
│   ├── services/         # trivia_service, iss_service, weather_service, analytics_service
│   └── utils/geo.py
├── static/                   # Web dashboard (served at /)
├── bruno/Personal API Hub/   # API test collection
├── tests/test_api.py
├── data/hub.db               # runtime (gitignored)
├── docs/PROJECT.md           # this file
├── Dockerfile
├── render.yaml               # Render free-tier deploy
├── requirements.txt
└── README.md
```

---

## 6. Database

**Path:** `data/hub.db` (relative to repo root, set in `app/config.py`)

**No manual setup.** Tables are created automatically via `init_db()` on startup and on first DB connection.

**Reset if corrupted:**
```bash
rm -f data/hub.db
# restart server
```

### Tables

**cache_entries**
- `id`, `source`, `data` (JSON text), `fetched_at`, `expires_at`, `fetch_duration_ms` (optional)
- Sources: `trivia`, `iss`, `weather`

**iss_positions**
- `id`, `latitude`, `longitude`, `fetched_at`
- Populated on each ISS refresh for distance analytics

---

## 7. Data sources and cache TTL

| Source | Config key | Upstream URL | TTL |
|--------|-----------|--------------|-----|
| trivia | `TRIVIA_API_URL` | opentdb.com | 3600s (1h) |
| iss | `ISS_API_URL` | api.open-notify.org (HTTP) | 300s (5m) |
| weather | `WEATHER_API_URL` | open-meteo.com (NYC) | 3600s (1h) |

### Upstream rate limits

Open-Meteo limits requests **per IP**. On shared hosts (e.g. Render), many apps share one IP, so bursts can return HTTP 429.

| Mitigation | Where |
|------------|-------|
| Cache TTL 1h for weather | `app/config.py` |
| Min 15 min between forced weather fetches | `app/utils/rate_limit.py` |
| Retry with backoff on 429/503 | `app/utils/http_client.py` |
| Serve stale cache when 429 and cache exists | `app/services/weather_service.py` |
| Stagger scheduler warm-up (weather +30s, iss +120s, trivia +240s) | `app/services/scheduler.py` |

When rate-limited with no cache, the API returns HTTP **429** (not 502) with a hint to retry later.

### Caching behavior (all sources)

| Request | Behavior |
|---------|----------|
| `GET /{source}` | Return cache if valid; else fetch + store |
| `GET /{source}?refresh=true` | Force fetch + store |
| `POST /{source}/refresh` | Force fetch + store |
| `GET /{source}/cached` | Cache only; 404 if empty |

---

## 8. API endpoints

### Root / UI
- `GET /` — web dashboard (static HTML)
- `GET /api` — JSON service index

### Health
- `GET /health` — always HTTP 200; `status`: `healthy` or `degraded`

### Data sources
Each of `/trivia`, `/iss`, `/weather` supports the caching pattern above.

### Analytics
| Endpoint | Purpose |
|----------|---------|
| `GET /analytics/summary` | Cross-source cache stats |
| `GET /analytics/trivia` | Difficulty/category/type breakdown |
| `GET /analytics/iss` | Position history + distance traveled (km) |
| `GET /analytics/weather` | 7-day trends, warmest/coldest/wettest days |
| `GET /analytics/daily-brief` | Cross-source brief: weather, ISS proximity, trivia question |
| `GET /analytics/cache-efficiency` | Per-source cache age, TTL, stale flag, hit-friendly status |

### Events (SSE)
| Endpoint | Purpose |
|----------|---------|
| `GET /events/stream` | SSE heartbeat every 30s + refresh completed/failed notices |

Interactive docs: http://localhost:8000/docs  
Dashboard: http://localhost:8000/

---

## 9. How to run

```bash
git checkout cursor/personal-api-data-hub-0354
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Verify
```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/trivia/refresh
curl http://localhost:8000/analytics/summary
```

### Tests
```bash
PYTHONPATH=. pytest tests/ -v
```

### Deploy (Render free tier)

1. Push this branch to GitHub
2. Create a **Web Service** on [Render](https://render.com/) and connect the repo
3. Use `render.yaml` (Blueprint) or manual settings:
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health check path:** `/health`
4. Open the service URL — dashboard at `/`, API at `/api`

> **Note:** Render free tier uses ephemeral disk. SQLite cache (`data/hub.db`) resets on redeploy/restart.

### Docker

```bash
docker build -t personal-api-hub .
docker run -p 8000:8000 personal-api-hub
```

---

## 10. Bruno collection

**Path:** `bruno/Personal API Hub/`
**Environment:** Local (`baseUrl` = `http://localhost:8000`)

When adding endpoints, add matching `.bru` files and update this section.

---

## 11. How to add a new feature (for agents)

Follow this checklist when the user requests a new data source, endpoint, or analytic.

### A. New data source (e.g. `/quotes`)

1. Add URL + TTL in `app/config.py`
2. Create `app/services/quotes_service.py` (copy pattern from `trivia_service.py`)
3. Create `app/routers/quotes.py` (copy pattern from `trivia.py`)
4. Register router in `app/main.py`
5. Add analytics method in `analytics_service.py` if requested
6. Add router in `app/routers/analytics.py` if needed
7. Add tests in `tests/test_api.py`
8. Add Bruno `.bru` files under `bruno/Personal API Hub/`
9. Update `README.md` and **this file**

### B. New analytics endpoint

1. Add method to `AnalyticsService` in `analytics_service.py`
2. Add route in `app/routers/analytics.py`
3. Add test + Bruno request
4. Update **this file**

### C. Code conventions

- Use `from __future__ import annotations` in every new Python module (Python 3.9 compat)
- Do not hold SQLite connections open during `await` HTTP calls (check cache, release, fetch, reconnect)
- Use `parse_utc_iso()` from `database.py` for all datetime parsing
- Upstream failures should raise `httpx.HTTPError` or `ValueError` (handled as 502)
- Health endpoint must always return HTTP 200

---

## 12. Known pitfalls (already fixed — do not reintroduce)

| Issue | Cause | Fix applied |
|-------|-------|-------------|
| Import crash on Python 3.9 | `dict[str] \| None` syntax | `from __future__ import annotations` |
| 500 on cached requests | Naive vs aware datetime compare | `parse_utc_iso()` helper |
| 500 on /health | Missing DB tables | Auto `init_db()` on connect |
| GitHub README blank | README saved as UTF-16 | Write README as UTF-8 |
| Opaque 500 errors | Unhandled exceptions | Global handler + logging |
| SQLite locked | DB held during HTTP await | Release connection before fetch |

---

## 13. Error response codes

| Code | Meaning |
|------|---------|
| 200 | Success (health always 200) |
| 404 | No cached data on `/{source}/cached` |
| 502 | Upstream API or validation failure (`detail` field) |
| 500 | Unexpected error (`detail` + traceback in terminal) |

---

## 14. Project history (changelog)

1. Initial build: FastAPI hub with trivia, ISS, weather + analytics
2. Bruno collection added (18 .bru files)
3. Rebrand: removed Java blog app, moved app to repo root, renamed to Personal API Hub
4. README rewritten; UTF-16 encoding fix
5. Python 3.9 compatibility fix
6. 500 fixes: datetime parsing, DB connection handling, error handlers
7. Health hardening: auto-init DB, always-200 health, server logging
8. This lookup file created
9. Tier 1: background scheduler, daily-brief, cache-efficiency, SSE stream, web UI, Render/Docker deploy

---

## 15. User preferences

- **Owner:** Deepak
- **Local OS tested:** macOS, Python 3.9
- **Repo name on GitHub:** still `blog-app`; user may rename to `personal-api-hub`
- **PR not yet merged to main**

---

## 16. Suggested next steps (not yet built)

- Merge feature branch to `main`
- Rename GitHub repo to `personal-api-hub`
- Additional data sources (user may request)
- Environment-based config via `.env` (not requested yet)
- Persistent volume on paid hosting for SQLite durability
