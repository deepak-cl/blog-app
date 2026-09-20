# RSS Headlines — World News, AI Developments & Entertainment

# World News & AI Developments — Implementation Plan

## Overview

Add two RSS-backed data sources to Personal API Hub: **World News** (`news`) and **AI Developments** (`ai_dev`). Both follow the existing cache-first service pattern (trivia/weather) with SQLite storage and APScheduler refresh.

## RSS Sources (free, no API keys)

### World News (`news`, TTL 3600s)

| Feed | URL |
|------|-----|
| BBC World | `https://feeds.bbci.co.uk/news/world/rss.xml` |
| NPR World | `https://feeds.npr.org/1004/rss.xml` |
| Al Jazeera English | `https://www.aljazeera.com/xml/rss/all.xml` |
| The Guardian World | `https://www.theguardian.com/world/rss` |

### AI Developments (`ai_dev`, TTL 7200s)

| Feed | URL |
|------|-----|
| Hugging Face Blog | `https://huggingface.co/blog/feed.xml` |
| OpenAI Blog | `https://openai.com/blog/rss.xml` |
| Google AI (Google Blog) | `https://blog.google/technology/ai/rss/` |
| arXiv cs.AI | `https://rss.arxiv.org/rss/cs.AI` |
| Anthropic News | `https://www.anthropic.com/news/rss` |

## Normalized payload

```json
{
  "headline_count": 20,
  "headlines": [
    {
      "title": "...",
      "summary": "...",
      "source": "BBC World",
      "url": "https://...",
      "published_at": "2026-09-20T08:00:00+00:00"
    }
  ]
}
```

- Dedupe by URL across feeds
- Sort by `published_at` descending
- Store up to 30 headlines per refresh

## Backend changes

| File | Change |
|------|--------|
| `requirements.txt` | Add `feedparser` |
| `app/config.py` | RSS feed URLs, `CACHE_TTL` for `news` / `ai_dev` |
| `app/services/rss_aggregator.py` | Shared RSS fetch + parse + normalize |
| `app/services/news_service.py` | `source = "news"` |
| `app/services/ai_dev_service.py` | `source = "ai_dev"` |
| `app/routers/news.py` | `GET/POST /news`, `/news/cached` |
| `app/routers/ai_dev.py` | `GET/POST /ai-dev`, `/ai-dev/cached` |
| `app/main.py` | Register routers, update `/api` index |
| `app/services/scheduler.py` | Add sources with stagger (news +360s, ai_dev +480s) |
| `app/services/analytics_service.py` | Extend `daily_brief`; add `news_brief()` |
| `app/routers/analytics.py` | `GET /analytics/news-brief` |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/news` | Cached headlines or refresh |
| GET | `/news?refresh=true` | Force refresh |
| POST | `/news/refresh` | Force refresh |
| GET | `/news/cached` | Cache only (404 if empty) |
| GET | `/ai-dev` | Same pattern |
| POST | `/ai-dev/refresh` | Force refresh |
| GET | `/ai-dev/cached` | Cache only |
| GET | `/analytics/news-brief` | Top headlines from news + ai_dev |
| GET | `/analytics/daily-brief` | Includes news + ai_dev snapshots |

## Dashboard (`static/`)

- **World News** card: top 5 headlines (title, source, link, time ago)
- **AI Developments** card: same layout
- Per-card refresh button, skeleton loading, existing dark theme CSS

## Tests & docs

- Mock RSS in `tests/test_api.py` for news/ai-dev fetch, cache, analytics
- Bruno folders: `News/`, `AI Dev/`
- Update `docs/PROJECT.md`

## Entertainment Headlines (`entertainment`, TTL 3600s)

| Feed | URL |
|------|-----|
| BBC Entertainment | `https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml` |
| Variety | `https://variety.com/feed/` |
| Hollywood Reporter | `https://www.hollywoodreporter.com/feed/` |
| NPR Arts | `https://feeds.npr.org/1008/rss.xml` |
| Guardian Culture | `https://www.theguardian.com/culture/rss` |

Endpoints: `GET/POST /entertainment`, `/entertainment/cached`. Scheduler stagger: +600s.

## Out of scope

- Celebrity/gossip tabloids
- Paid APIs (GNews optional key not implemented)
- LLM summarization (optional enhancement deferred)
- Photos/images in dashboard cards
