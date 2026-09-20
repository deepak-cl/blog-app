from __future__ import annotations

import time

import httpx

from app.config import CACHE_TTL, ISS_API_URL
from app.db.database import (
    get_connection,
    get_latest_cache_entry,
    is_cache_valid,
    save_cache_entry,
    save_iss_position,
    utc_now_iso,
)


class ISSService:
    source = "iss"

    async def fetch_remote(self) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(ISS_API_URL)
            response.raise_for_status()
            payload = response.json()

        position = payload["iss_position"]
        return {
            "latitude": float(position["latitude"]),
            "longitude": float(position["longitude"]),
            "timestamp": payload.get("timestamp"),
            "message": payload.get("message", "success"),
        }

    async def get_or_refresh(self, force: bool = False) -> dict:
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
        fetched_at = utc_now_iso()

        with get_connection() as conn:
            save_iss_position(conn, data["latitude"], data["longitude"], fetched_at)
            result = save_cache_entry(
                conn,
                self.source,
                data,
                CACHE_TTL[self.source],
                fetch_duration_ms=fetch_duration_ms,
            )
            result["fetched_at"] = fetched_at
            return result

    def get_cached(self) -> dict | None:
        with get_connection() as conn:
            cached = get_latest_cache_entry(conn, self.source)
            if cached is None:
                return None
            return {
                **cached,
                "from_cache": True,
                "cache_valid": is_cache_valid(cached),
            }
