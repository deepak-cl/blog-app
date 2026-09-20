from __future__ import annotations

import time

# Minimum seconds between upstream HTTP calls per source (avoids 429 on shared hosts)
UPSTREAM_MIN_INTERVAL = {
    "trivia": 300,
    "iss": 60,
    "weather": 900,
}

_last_upstream_fetch: dict[str, float] = {}


def should_skip_upstream(source: str, *, force: bool, has_cache: bool) -> bool:
    """Skip upstream fetch if called too soon; always fetch when cache is empty."""
    if not has_cache:
        return False
    if not force:
        return False

    min_interval = UPSTREAM_MIN_INTERVAL.get(source, 60)
    last = _last_upstream_fetch.get(source)
    if last is None:
        return False
    return (time.monotonic() - last) < min_interval


def mark_upstream_fetch(source: str) -> None:
    _last_upstream_fetch[source] = time.monotonic()
