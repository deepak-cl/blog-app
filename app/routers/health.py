from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import CACHE_TTL, DATABASE_PATH
from app.db.database import get_cache_stats, get_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    db_ok = DATABASE_PATH.exists()
    if not db_ok:
        with get_connection():
            db_ok = True

    with get_connection() as conn:
        stats = get_cache_stats(conn)

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
