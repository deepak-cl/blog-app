from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import CACHE_TTL, DATABASE_PATH
from app.db.database import get_cache_stats, get_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    try:
        db_ok = DATABASE_PATH.exists()
        if not db_ok:
            with get_connection():
                db_ok = True

        with get_connection() as conn:
            stats = get_cache_stats(conn)
    except Exception as exc:
        return {
            "status": "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": {
                "path": str(DATABASE_PATH),
                "connected": False,
                "error": str(exc),
            },
            "cache_ttl_seconds": CACHE_TTL,
            "cache_stats": {"sources": [], "iss_position_samples": 0},
        }

    return {
        "status": "healthy" if db_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {
            "path": str(DATABASE_PATH),
            "connected": db_ok,
        },
        "cache_ttl_seconds": CACHE_TTL,
        "cache_stats": stats,
    }
