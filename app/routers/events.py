from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.config import SSE_HEARTBEAT_SECONDS
from app.services.analytics_service import AnalyticsService
from app.services.event_bus import event_bus

router = APIRouter(prefix="/events", tags=["events"])
analytics = AnalyticsService()


async def _event_stream():
    queue = await event_bus.subscribe()
    try:
        while True:
            try:
                event = await asyncio.wait_for(
                    queue.get(), timeout=SSE_HEARTBEAT_SECONDS
                )
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                heartbeat = {
                    "type": "heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": {
                        "health": analytics.health_summary(),
                        "cache_stats": analytics.cache_stats_snapshot(),
                    },
                }
                yield f"data: {json.dumps(heartbeat)}\n\n"
    finally:
        event_bus.unsubscribe(queue)


@router.get("/stream")
async def stream_events():
    """Server-Sent Events stream with health, cache stats, and refresh notices."""
    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
