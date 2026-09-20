from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any

import feedparser
import httpx

from app.db.database import (
    get_connection,
    get_latest_cache_entry,
    is_cache_valid,
    save_cache_entry,
)

logger = logging.getLogger(__name__)

MAX_HEADLINES = 30
FETCH_TIMEOUT = 20.0


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = unescape(value)
    # Minimal tag removal for RSS summaries
    while "<" in text and ">" in text:
        start = text.find("<")
        end = text.find(">", start)
        if end == -1:
            break
        text = text[:start] + text[end + 1 :]
    return " ".join(text.split())


def _parse_published(entry: dict[str, Any]) -> str | None:
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            try:
                dt = datetime(*parsed[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except (TypeError, ValueError):
                continue

    for key in ("published", "updated"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            continue
    return None


def _entry_url(entry: dict[str, Any]) -> str | None:
    link = entry.get("link")
    if link:
        return link
    links = entry.get("links") or []
    for item in links:
        if item.get("rel") == "alternate" and item.get("href"):
            return item["href"]
    return links[0].get("href") if links else None


class RssAggregatorService:
    """Fetch and aggregate RSS feeds into a normalized headline list."""

    def __init__(
        self,
        source: str,
        feeds: list[dict[str, str]],
        ttl_seconds: int,
    ) -> None:
        self.source = source
        self.feeds = feeds
        self.ttl_seconds = ttl_seconds

    async def _fetch_feed(
        self, client: httpx.AsyncClient, feed: dict[str, str]
    ) -> list[dict[str, Any]]:
        name = feed["name"]
        url = feed["url"]
        try:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
        except Exception as exc:
            logger.warning("RSS feed failed source=%s feed=%s error=%s", self.source, name, exc)
            return []

        headlines: list[dict[str, Any]] = []
        for entry in parsed.entries:
            title = _strip_html(entry.get("title"))
            url_value = _entry_url(entry)
            if not title or not url_value:
                continue

            content_items = entry.get("content") or []
            content_value = content_items[0].get("value") if content_items else None
            summary = _strip_html(
                entry.get("summary") or entry.get("description") or content_value
            )
            published_at = _parse_published(entry)

            headlines.append(
                {
                    "title": title,
                    "summary": summary[:500] if summary else "",
                    "source": name,
                    "url": url_value,
                    "published_at": published_at,
                }
            )
        return headlines

    async def fetch_remote(self) -> dict[str, Any]:
        all_headlines: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        async with httpx.AsyncClient(
            timeout=FETCH_TIMEOUT,
            headers={"User-Agent": "PersonalAPIHub/1.0 (RSS aggregator)"},
        ) as client:
            for feed in self.feeds:
                for item in await self._fetch_feed(client, feed):
                    url = item["url"]
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    all_headlines.append(item)

        if not all_headlines:
            raise ValueError(f"No headlines fetched for source={self.source}")

        def sort_key(row: dict[str, Any]) -> tuple[int, str]:
            published = row.get("published_at")
            if published:
                return (1, published)
            return (0, "")

        all_headlines.sort(key=sort_key, reverse=True)
        trimmed = all_headlines[:MAX_HEADLINES]

        return {
            "headline_count": len(trimmed),
            "headlines": trimmed,
            "feed_count": len(self.feeds),
        }

    async def get_or_refresh(self, force: bool = False) -> dict[str, Any]:
        with get_connection() as conn:
            cached = get_latest_cache_entry(conn, self.source)
            if not force and is_cache_valid(cached):
                return {
                    **cached,
                    "from_cache": True,
                }

        start = time.monotonic()
        data = await self.fetch_remote()
        fetch_duration_ms = int((time.monotonic() - start) * 1000)

        with get_connection() as conn:
            return save_cache_entry(
                conn,
                self.source,
                data,
                self.ttl_seconds,
                fetch_duration_ms=fetch_duration_ms,
            )

    def get_cached(self) -> dict[str, Any] | None:
        with get_connection() as conn:
            cached = get_latest_cache_entry(conn, self.source)
            if cached is None:
                return None
            return {
                **cached,
                "from_cache": True,
                "cache_valid": is_cache_valid(cached),
            }
