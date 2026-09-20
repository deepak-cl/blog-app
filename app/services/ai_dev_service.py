from __future__ import annotations

from app.config import AI_DEV_RSS_FEEDS, CACHE_TTL
from app.services.rss_aggregator import RssAggregatorService


class AiDevService(RssAggregatorService):
    source = "ai_dev"

    def __init__(self) -> None:
        super().__init__(
            source=self.source,
            feeds=AI_DEV_RSS_FEEDS,
            ttl_seconds=CACHE_TTL[self.source],
        )
