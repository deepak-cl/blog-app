from __future__ import annotations

import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import CACHE_TTL, DATABASE_PATH
from app.db.database import get_connection, init_db

_lock = threading.Lock()
_request_counts: dict[tuple[str, str, str], int] = defaultdict(int)
_cache_hits: dict[str, int] = defaultdict(int)
_cache_misses: dict[str, int] = defaultdict(int)

_PATH_NORMALIZER = re.compile(r"/[0-9a-f-]{8,}", re.IGNORECASE)


def normalize_path(path: str) -> str:
    if path == "/metrics":
        return "/metrics"
    if path.startswith("/docs") or path.startswith("/redoc") or path.startswith("/openapi"):
        return "/docs"
    normalized = _PATH_NORMALIZER.sub("", path)
    return normalized.rstrip("/") or "/"


def record_cache_hit(source: str) -> None:
    with _lock:
        _cache_hits[source] += 1


def record_cache_miss(source: str) -> None:
    with _lock:
        _cache_misses[source] += 1


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        path = normalize_path(request.url.path)
        key = (request.method, path, str(response.status_code))
        with _lock:
            _request_counts[key] += 1
        response.headers["X-Response-Time-Ms"] = f"{duration * 1000:.1f}"
        return response


def _prometheus_line(name: str, value: float | int, labels: dict[str, str] | None = None) -> str:
    if labels:
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}} {value}"
    return f"{name} {value}"


def collect_prometheus_metrics() -> str:
    lines: list[str] = []

    with _lock:
        for (method, path, status), count in sorted(_request_counts.items()):
            lines.append(
                _prometheus_line(
                    "http_requests_total",
                    count,
                    {"method": method, "path": path, "status": status},
                )
            )
        for source, count in sorted(_cache_hits.items()):
            lines.append(
                _prometheus_line("cache_hits_total", count, {"source": source})
            )
        for source, count in sorted(_cache_misses.items()):
            lines.append(
                _prometheus_line("cache_misses_total", count, {"source": source})
            )

    health_status = 0.0
    last_fetch: dict[str, str | None] = {source: None for source in CACHE_TTL}

    try:
        init_db()
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT source, MAX(fetched_at) AS last_fetched
                FROM cache_entries
                GROUP BY source
                """
            ).fetchall()
            for row in rows:
                last_fetch[row["source"]] = row["last_fetched"]

        health_status = 1.0 if DATABASE_PATH.exists() else 0.0
    except Exception:
        health_status = 0.0

    lines.append(_prometheus_line("hub_health_status", health_status))

    for source, ttl in CACHE_TTL.items():
        fetched_at = last_fetch.get(source)
        if fetched_at:
            try:
                ts = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                epoch = ts.timestamp()
            except ValueError:
                epoch = 0.0
        else:
            epoch = 0.0
        lines.append(
            _prometheus_line(
                "cache_last_fetch_timestamp_seconds",
                epoch,
                {"source": source},
            )
        )
        lines.append(
            _prometheus_line(
                "cache_ttl_seconds",
                ttl,
                {"source": source},
            )
        )

    lines.append(
        _prometheus_line(
            "metrics_scrape_timestamp_seconds",
            datetime.now(timezone.utc).timestamp(),
        )
    )

    return "\n".join(lines) + "\n"
