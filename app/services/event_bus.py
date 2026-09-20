from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any


class EventBus:
    """In-memory pub/sub for SSE clients and scheduler refresh notices."""

    def __init__(self, max_history: int = 100) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._history: deque[dict[str, Any]] = deque(maxlen=max_history)

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        self._history.append(event)
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        return list(self._history)[-limit:]

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=50)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)


event_bus = EventBus()
