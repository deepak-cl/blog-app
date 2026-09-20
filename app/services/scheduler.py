from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import CACHE_TTL, SCHEDULER_ENABLED
from app.services.event_bus import event_bus
from app.services.iss_service import ISSService
from app.services.trivia_service import TriviaService
from app.services.weather_service import WeatherService

logger = logging.getLogger(__name__)

SOURCES = ("weather", "iss", "trivia")
STARTUP_STAGGER_SECONDS = {"weather": 30, "iss": 120, "trivia": 240}
WARM_STAGGER_SECONDS = 45


class RefreshScheduler:
    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._trivia = TriviaService()
        self._iss = ISSService()
        self._weather = WeatherService()

    async def refresh_source(self, source: str) -> dict[str, Any]:
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
            return {"source": source, "status": "ok", "duration_ms": duration_ms}
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
            return {"source": source, "status": "error", "error": str(exc), "duration_ms": duration_ms}

    async def warm_all_sources(self) -> list[dict[str, Any]]:
        """Fetch sources sequentially with delay to avoid upstream 429 bursts."""
        results: list[dict[str, Any]] = []
        for index, source in enumerate(SOURCES):
            if index > 0:
                await asyncio.sleep(WARM_STAGGER_SECONDS)
            results.append(await self.refresh_source(source))
        return results

    def start(self) -> None:
        if not SCHEDULER_ENABLED:
            logger.info("Background refresh scheduler disabled")
            return

        now = datetime.now(timezone.utc)
        for source in SOURCES:
            ttl = CACHE_TTL[source]
            stagger = STARTUP_STAGGER_SECONDS.get(source, 0)
            self._scheduler.add_job(
                self.refresh_source,
                trigger="interval",
                seconds=ttl,
                args=[source],
                id=f"refresh_{source}",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                next_run_time=now + timedelta(seconds=stagger),
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
