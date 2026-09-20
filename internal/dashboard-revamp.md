# Dashboard Revamp — Implementation Notes

## Scope

Overhauled the Personal API Hub dashboard (`static/`) while keeping backend endpoints intact. Merged latest `main` (includes Anekal/Bengaluru localization from prior work).

## UI removals (backend kept)

| Removed from UI | Backend endpoint |
|-----------------|------------------|
| Cache efficiency panel | `GET /analytics/cache-efficiency` |
| Live SSE feed | `GET /events/stream` |

## UI additions

- **Theme toggle** — sun/moon button in header; `localStorage` key `pah-theme`; falls back to `prefers-color-scheme`
- **CSS variables** — separate light/dark palettes in `styles.css` via `html[data-theme]`
- **Interactive cards** — Weather, ISS, Trivia with skeleton loaders, hover lift, per-card refresh (`POST /{source}/refresh`)
- **AI Daily Brief card** — provider dropdown (from `/analytics/ai-brief/providers`), Generate button, spinner + skeleton loading state
- **Location label** — subtitle and weather cards use cached `Anekal, Bengaluru` data from backend config

## AI Daily Brief backend

| File | Role |
|------|------|
| `app/services/ai_brief_service.py` | Builds prompt from `AnalyticsService.daily_brief()`, calls provider via httpx |
| `app/routers/analytics.py` | Routes: `GET/POST /analytics/ai-brief`, `GET /analytics/ai-brief/providers` |

### Env vars (Render / local)

| Variable | Provider |
|----------|----------|
| `OPENAI_API_KEY` | OpenAI (`gpt-4o-mini`) |
| `ANTHROPIC_API_KEY` | Anthropic (`claude-3-5-haiku-20241022`) |
| `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Gemini (`gemini-2.0-flash`) |

- No keys → HTTP **503** with setup message; UI shows hint
- Keys are never logged or committed
- Token cap: `max_tokens` / `maxOutputTokens` = 150

## Tests

Added in `tests/test_api.py`:

- `test_ai_brief_providers_empty` — no env keys → empty provider list
- `test_ai_brief_no_key_configured` — POST returns 503
- `test_ai_brief_missing_provider_key` — specific provider without key → 503

## Docs / Bruno

- `docs/PROJECT.md` — theme, AI brief, dashboard behavior
- `bruno/Personal API Hub/Analytics/analytics-ai-brief*.bru` — new requests
- `render.yaml` — commented optional AI env var keys
