from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.metrics import collect_prometheus_metrics

router = APIRouter(tags=["observability"])


@router.get("/metrics")
def prometheus_metrics():
    """Prometheus-compatible metrics for admin scraping (not linked from dashboard)."""
    return PlainTextResponse(
        content=collect_prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
