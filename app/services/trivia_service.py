from __future__ import annotations

import time

import httpx

from app.config import CACHE_TTL, TRIVIA_API_URL
from app.db.database import (
    get_connection,
    get_latest_cache_entry,
    is_cache_valid,
    save_cache_entry,
)


class TriviaService:
    source = "trivia"

    async def fetch_remote(self) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(TRIVIA_API_URL)
            response.raise_for_status()
            payload = response.json()

        if payload.get("response_code") != 0:
            raise ValueError(f"Trivia API error: response_code={payload.get('response_code')}")

        questions = payload.get("results", [])
        return {
            "question_count": len(questions),
            "questions": [
                {
                    "category": q.get("category"),
                    "type": q.get("type"),
                    "difficulty": q.get("difficulty"),
                    "question": q.get("question"),
                    "correct_answer": q.get("correct_answer"),
                    "incorrect_answers": q.get("incorrect_answers", []),
                }
                for q in questions
            ],
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

        with get_connection() as conn:
            return save_cache_entry(
                conn,
                self.source,
                data,
                CACHE_TTL[self.source],
                fetch_duration_ms=fetch_duration_ms,
            )

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
