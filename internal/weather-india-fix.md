# Weather & AI fixes for Bengaluru (India)

Date: 2026-09-20  
Location: Anekal, Bengaluru (`12.7081`, `77.6953`)

## Live failures (root causes)

| Symptom | Root cause |
| --- | --- |
| `POST /weather/refresh` → 429 | Open-Meteo rate-limits shared Render egress IPs; NWS fallback is US-only and skipped for Bengaluru |
| Anthropic AI brief → 404 | Deprecated model ID `claude-3-5-haiku-20241022` (no longer served at `/v1/messages`) |
| Raw `httpx` errors in UI | API/frontend surfaced exception strings instead of user-facing messages |

## Fixes applied

1. **Anthropic model** → `claude-haiku-4-5` (current cheap Haiku alias per [Anthropic docs](https://docs.anthropic.com/en/docs/about-claude/models))
2. **Weather provider chain** (try in order, stop on first success):
   - Open-Meteo (primary, 5 retries, **2h cache TTL**)
   - **IMD** when `IMD_API_KEY` set (India-native, `X-API-Key` header)
   - **OpenWeatherMap** when `OPENWEATHER_API_KEY` set (global free tier)
   - NWS when coordinates are in the US
   - **wttr.in** last-resort free global fallback (`format=j1`)
3. **Stale cache** served when all providers fail but cache exists
4. **Friendly errors** via `app/utils/errors.py` + dashboard `parseApiError()`

## Indian weather API options researched

| Provider | Cost | Bengaluru | Notes |
| --- | --- | --- | --- |
| **Open-Meteo** | Free, no key | Yes (lat/lon) | Best default; **429 common on Render** shared IP |
| **IMD** ([api.imd.gov.in](https://api.imd.gov.in/public/index.php)) | **Free registration** | Yes | Official India data; `X-API-Key` required (401 without). Register at portal. Bengaluru city id **42182**. Endpoints: `/api/v1/cityforecastloc`, `/api/v1/cityforecast`, `/api/v1/current_wx`. May also require IP whitelisting for some accounts — contact IMD support if needed |
| **OpenWeatherMap** | Free tier (~1M calls/month) | Yes | Global; `OPENWEATHER_API_KEY`; reliable fallback |
| **wttr.in** | Free, no key | Yes | Last-resort; uses WorldWeatherOnline backend; good for dev/low traffic |
| **Visual Crossing** | Free tier (1000/day) | Yes | Not wired in — optional future fallback if user adds `VISUALCROSSING_API_KEY` |
| **Skymet** | Commercial / limited public API | Yes | No stable free public REST API for hobby dashboards |
| **IMD Mausamgram** | App-focused | Yes | Mobile/web product; not a simple REST substitute for hub caching |

### IMD registration

- Portal: https://api.imd.gov.in/public/index.php
- Create account → obtain API key → set on Render:
  - `IMD_API_KEY` (secret)
  - `IMD_CITY_ID=42182` (Bengaluru; optional override)
- Header format confirmed: `X-API-Key: <your-key>`

### OpenWeatherMap (optional)

- Sign up: https://openweathermap.org/api
- Free tier: global current + 5-day/3-hour forecast
- Set `OPENWEATHER_API_KEY` on Render

## Recommended setup for India (Render)

**Minimum (no keys):** Open-Meteo + wttr.in fallback + 2h cache — works but may hit 429 on cold refresh during peak Render traffic.

**Recommended for Bengaluru:**

```yaml
# render.yaml (uncomment and set in dashboard)
IMD_API_KEY: <free key from api.imd.gov.in>
IMD_CITY_ID: "42182"
OPENWEATHER_API_KEY: <optional second fallback>
ANTHROPIC_API_KEY: <existing — now uses claude-haiku-4-5>
```

Priority: **IMD** (official, India-tuned) → Open-Meteo (when not rate-limited) → OpenWeather → wttr.in.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `IMD_API_KEY` | Optional | India Meteorological Department forecast |
| `IMD_CITY_ID` | Optional | Default `42182` (Bengaluru) |
| `OPENWEATHER_API_KEY` | Optional | Global OpenWeather fallback |
| `ANTHROPIC_API_KEY` | Optional | AI brief (Haiku 4.5) |
