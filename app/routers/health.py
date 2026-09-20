from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import CACHE_TTL, DATABASE_PATH
from app.db.database import get_cache_stats, get_connection, init_db

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
def health_check():
    """Always returns HTTP 200; inspect status field for service health."""
    try:
        init_db()

        with get_connection() as conn:
            stats = get_cache_stats(conn)

        payload = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": {
                "path": str(DATABASE_PATH),
                "connected": True,
                "exists": DATABASE_PATH.exists(),
            },
            "cache_ttl_seconds": CACHE_TTL,
            "cache_stats": stats,
        }
        return JSONResponse(status_code=200, content=payload)
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        logger.debug(traceback.format_exc())
        payload = {
            "status": "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": {
                "path": str(DATABASE_PATH),
                "connected": False,
                "exists": DATABASE_PATH.exists(),
                "error": str(exc),
            },
            "cache_ttl_seconds": CACHE_TTL,
            "cache_stats": {"sources": [], "iss_position_samples": 0},
        }
        return JSONResponse(status_code=200, content=payload)
