from __future__ import annotations

import logging
import time
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import CACHE_TTL, SCHEDULER_ENABLED
from app.services.event_bus import event_bus
from app.services.iss_service import ISSService
from app.services.trivia_service import TriviaService
from app.services.weather_service import WeatherService

logger = logging.getLogger(__name__)

SOURCES = ("trivia", "iss", "weather")


class RefreshScheduler:
    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._trivia = TriviaService()
        self._iss = ISSService()
        self._weather = WeatherService()

    async def refresh_source(self, source: str) -> None:
        start = time.monotonic()
        try:
            if source == "trivia":
                result = await self._trivia.get_or_refresh(force=True)
            elif source == "iss":
                result = await self._iss.get_or_refresh(force=True)
            elif source == "weather":
                result = await self._weather.get_or_refresh(force=True)
            else:
                raise ValueError(f"Unknown source: {source}")

            duration_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "Scheduled refresh completed source=%s duration_ms=%s from_cache=%s",
                source,
                duration_ms,
                result.get("from_cache", False),
            )
            event_bus.publish(
                "refresh_completed",
                {
                    "source": source,
                    "duration_ms": duration_ms,
                    "fetched_at": result.get("fetched_at"),
                },
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "Scheduled refresh failed source=%s duration_ms=%s",
                source,
                duration_ms,
            )
            event_bus.publish(
                "refresh_failed",
                {
                    "source": source,
                    "duration_ms": duration_ms,
                    "error": str(exc),
                },
            )

    def start(self) -> None:
        if not SCHEDULER_ENABLED:
            logger.info("Background refresh scheduler disabled")
            return

        for source in SOURCES:
            ttl = CACHE_TTL[source]
            self._scheduler.add_job(
                self.refresh_source,
                trigger="interval",
                seconds=ttl,
                args=[source],
                id=f"refresh_{source}",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            logger.info(
                "Scheduled background refresh source=%s interval_seconds=%s",
                source,
                ttl,
            )

        self._scheduler.start()
        logger.info("Background refresh scheduler started")

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Background refresh scheduler stopped")


refresh_scheduler = RefreshScheduler()
