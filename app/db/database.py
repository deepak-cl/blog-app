from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from app.config import DATABASE_PATH


def _ensure_data_dir() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    _ensure_data_dir()
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS cache_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                data TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_cache_source_fetched
                ON cache_entries(source, fetched_at DESC);

            CREATE TABLE IF NOT EXISTS iss_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                fetched_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_iss_fetched
                ON iss_positions(fetched_at DESC);
            """
        )


@contextmanager
def get_connection():
    _ensure_data_dir()
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_utc_iso(value: str) -> datetime:
    """Parse ISO timestamps from SQLite; normalize naive values to UTC."""
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def save_cache_entry(
    conn: sqlite3.Connection,
    source: str,
    data: dict[str, Any],
    ttl_seconds: int,
) -> dict[str, Any]:
    fetched_at = utc_now_iso()
    expires_at = parse_utc_iso(fetched_at).timestamp() + ttl_seconds
    expires_at_iso = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()

    conn.execute(
        """
        INSERT INTO cache_entries (source, data, fetched_at, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (source, json.dumps(data), fetched_at, expires_at_iso),
    )
    return {
        "source": source,
        "data": data,
        "fetched_at": fetched_at,
        "expires_at": expires_at_iso,
        "from_cache": False,
    }


def get_latest_cache_entry(
    conn: sqlite3.Connection, source: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, source, data, fetched_at, expires_at
        FROM cache_entries
        WHERE source = ?
        ORDER BY fetched_at DESC
        LIMIT 1
        """,
        (source,),
    ).fetchone()

    if row is None:
        return None

    return {
        "id": row["id"],
        "source": row["source"],
        "data": json.loads(row["data"]),
        "fetched_at": row["fetched_at"],
        "expires_at": row["expires_at"],
    }


def is_cache_valid(entry: dict[str, Any] | None) -> bool:
    if entry is None:
        return False
    try:
        expires_at = parse_utc_iso(entry["expires_at"])
    except (TypeError, ValueError):
        return False
    return datetime.now(timezone.utc) <= expires_at


def save_iss_position(
    conn: sqlite3.Connection, latitude: float, longitude: float, fetched_at: str
) -> None:
    conn.execute(
        """
        INSERT INTO iss_positions (latitude, longitude, fetched_at)
        VALUES (?, ?, ?)
        """,
        (latitude, longitude, fetched_at),
    )


def get_iss_position_history(
    conn: sqlite3.Connection, limit: int = 100
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT latitude, longitude, fetched_at
        FROM iss_positions
        ORDER BY fetched_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "fetched_at": row["fetched_at"],
        }
        for row in rows
    ]


def get_cache_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT source,
               COUNT(*) AS entry_count,
               MAX(fetched_at) AS last_fetched
        FROM cache_entries
        GROUP BY source
        """
    ).fetchall()

    iss_count = conn.execute("SELECT COUNT(*) AS count FROM iss_positions").fetchone()

    return {
        "sources": [
            {
                "source": row["source"],
                "entry_count": row["entry_count"],
                "last_fetched": row["last_fetched"],
            }
            for row in rows
        ],
        "iss_position_samples": iss_count["count"] if iss_count else 0,
    }
