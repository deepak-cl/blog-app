from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
MAX_RETRIES = 3
RETRY_BASE_SECONDS = 2.0


async def get_json(
    url: str,
    *,
    timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    retries: int = MAX_RETRIES,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """GET JSON with retries on 429/503 and exponential backoff."""
    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for attempt in range(retries):
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 429:
                    retry_after = _retry_after_seconds(response)
                    logger.warning(
                        "Rate limited url=%s attempt=%s retry_after=%ss",
                        url,
                        attempt + 1,
                        retry_after,
                    )
                    if attempt + 1 >= retries:
                        response.raise_for_status()
                    await asyncio.sleep(retry_after)
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code in {429, 503} and attempt + 1 < retries:
                    await asyncio.sleep(RETRY_BASE_SECONDS * (2**attempt))
                    continue
                raise
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt + 1 < retries:
                    await asyncio.sleep(RETRY_BASE_SECONDS * (2**attempt))
                    continue
                raise

    if last_error:
        raise last_error
    raise RuntimeError(f"Failed to fetch {url}")


def _retry_after_seconds(response: httpx.Response) -> float:
    header = response.headers.get("Retry-After")
    if header and header.isdigit():
        return float(header)
    return RETRY_BASE_SECONDS * 2
