from __future__ import annotations

from app.config import CACHE_TTL, NEWS_RSS_FEEDS
from app.services.rss_aggregator import RssAggregatorService


class NewsService(RssAggregatorService):
    source = "news"

    def __init__(self) -> None:
        super().__init__(
            source=self.source,
            feeds=NEWS_RSS_FEEDS,
            ttl_seconds=CACHE_TTL[self.source],
        )
