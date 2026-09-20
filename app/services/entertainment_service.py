from __future__ import annotations

from app.config import CACHE_TTL, ENTERTAINMENT_RSS_FEEDS
from app.services.rss_aggregator import RssAggregatorService


class EntertainmentService(RssAggregatorService):
    source = "entertainment"

    def __init__(self) -> None:
        super().__init__(
            source=self.source,
            feeds=ENTERTAINMENT_RSS_FEEDS,
            ttl_seconds=CACHE_TTL[self.source],
        )
