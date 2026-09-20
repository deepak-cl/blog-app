from __future__ import annotations

import random
from collections import Counter
from datetime import datetime, timezone

from app.config import (
    CACHE_TTL,
    ISS_NEAR_THRESHOLD_KM,
    ISS_REFERENCE_LABEL,
    ISS_REFERENCE_LAT,
    ISS_REFERENCE_LNG,
)
from app.db.database import (
    get_connection,
    get_iss_position_history,
    get_latest_cache_entry,
    get_per_source_cache_summary,
    parse_utc_iso,
)
from app.utils.geo import haversine_km


def _headline_snapshot(entry: dict | None, *, limit: int = 3) -> dict | None:
    if entry is None:
        return None
    headlines = entry["data"].get("headlines", [])[:limit]
    if not headlines:
        return None
    return {
        "cached_at": entry["fetched_at"],
        "headline_count": entry["data"].get("headline_count", len(headlines)),
        "top_headlines": [
            {
                "title": row.get("title"),
                "source": row.get("source"),
                "url": row.get("url"),
                "published_at": row.get("published_at"),
            }
            for row in headlines
        ],
    }


class AnalyticsService:
    def summary(self) -> dict:
        with get_connection() as conn:
            stats = conn.execute(
                """
                SELECT source, COUNT(*) AS entries, MAX(fetched_at) AS last_fetched
                FROM cache_entries
                GROUP BY source
                """
            ).fetchall()

            iss_samples = conn.execute(
                "SELECT COUNT(*) AS count FROM iss_positions"
            ).fetchone()

        sources = {
            row["source"]: {
                "cached_entries": row["entries"],
                "last_fetched": row["last_fetched"],
            }
            for row in stats
        }

        return {
            "total_cache_entries": sum(row["entries"] for row in stats),
            "sources": sources,
            "iss_position_samples": iss_samples["count"] if iss_samples else 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def trivia_breakdown(self) -> dict:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT data FROM cache_entries
                WHERE source = 'trivia'
                ORDER BY fetched_at DESC
                LIMIT 1
                """
            ).fetchone()

        if row is None:
            return {"error": "No trivia data cached. Fetch trivia first."}

        import json

        data = json.loads(row["data"])
        questions = data.get("questions", [])

        by_difficulty = Counter(q.get("difficulty", "unknown") for q in questions)
        by_category = Counter(q.get("category", "unknown") for q in questions)
        by_type = Counter(q.get("type", "unknown") for q in questions)

        return {
            "question_count": len(questions),
            "by_difficulty": dict(by_difficulty),
            "by_category": dict(by_category),
            "by_type": dict(by_type),
            "hardest_questions": [
                q["question"]
                for q in questions
                if q.get("difficulty") == "hard"
            ][:3],
        }

    def iss_history(self, limit: int = 50) -> dict:
        with get_connection() as conn:
            history = get_iss_position_history(conn, limit=limit)

        if len(history) < 2:
            return {
                "sample_count": len(history),
                "positions": history,
                "distance_traveled_km": 0.0,
                "note": "Need at least 2 ISS samples to estimate distance.",
            }

        # History is newest-first; reverse for chronological travel
        chronological = list(reversed(history))
        total_km = 0.0
        segments = []

        for i in range(1, len(chronological)):
            prev = chronological[i - 1]
            curr = chronological[i]
            segment_km = haversine_km(
                prev["latitude"],
                prev["longitude"],
                curr["latitude"],
                curr["longitude"],
            )
            total_km += segment_km
            segments.append(
                {
                    "from": prev["fetched_at"],
                    "to": curr["fetched_at"],
                    "distance_km": round(segment_km, 2),
                }
            )

        latest = history[0]
        return {
            "sample_count": len(history),
            "latest_position": latest,
            "distance_traveled_km": round(total_km, 2),
            "average_segment_km": round(total_km / len(segments), 2) if segments else 0,
            "segments": segments[-10:],
        }

    def weather_trends(self) -> dict:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT data, fetched_at FROM cache_entries
                WHERE source = 'weather'
                ORDER BY fetched_at DESC
                LIMIT 1
                """
            ).fetchone()

        if row is None:
            return {"error": "No weather data cached. Fetch weather first."}

        import json

        data = json.loads(row["data"])
        forecast = data.get("forecast_7d", {})
        dates = forecast.get("dates", [])
        max_temps = forecast.get("temperature_max_c", [])
        min_temps = forecast.get("temperature_min_c", [])
        precip = forecast.get("precipitation_mm", [])

        if not dates:
            return {"error": "Weather forecast data is empty."}

        daily = []
        for i, date in enumerate(dates):
            daily.append(
                {
                    "date": date,
                    "max_c": max_temps[i] if i < len(max_temps) else None,
                    "min_c": min_temps[i] if i < len(min_temps) else None,
                    "precipitation_mm": precip[i] if i < len(precip) else None,
                    "spread_c": (
                        round(max_temps[i] - min_temps[i], 1)
                        if i < len(max_temps) and i < len(min_temps)
                        else None
                    ),
                }
            )

        valid_max = [t for t in max_temps if t is not None]
        valid_min = [t for t in min_temps if t is not None]
        valid_precip = [p for p in precip if p is not None]

        warmest_day = dates[max_temps.index(max(valid_max))] if valid_max else None
        coldest_day = dates[min_temps.index(min(valid_min))] if valid_min else None
        wettest_day = (
            dates[precip.index(max(valid_precip))]
            if valid_precip and max(valid_precip) > 0
            else None
        )

        return {
            "location": data.get("location"),
            "cached_at": row["fetched_at"],
            "current": data.get("current"),
            "daily_forecast": daily,
            "summary": {
                "avg_high_c": round(sum(valid_max) / len(valid_max), 1) if valid_max else None,
                "avg_low_c": round(sum(valid_min) / len(valid_min), 1) if valid_min else None,
                "total_precipitation_mm": round(sum(valid_precip), 1) if valid_precip else None,
                "warmest_day": warmest_day,
                "coldest_day": coldest_day,
                "wettest_day": wettest_day,
            },
        }

    def daily_brief(
        self,
        *,
        reference_lat: float = ISS_REFERENCE_LAT,
        reference_lng: float = ISS_REFERENCE_LNG,
        near_threshold_km: float = ISS_NEAR_THRESHOLD_KM,
    ) -> dict:
        now = datetime.now(timezone.utc)
        weather_snapshot: dict | None = None
        iss_snapshot: dict | None = None
        trivia_snapshot: dict | None = None
        news_snapshot: dict | None = None
        ai_dev_snapshot: dict | None = None
        entertainment_snapshot: dict | None = None
        notes: list[str] = []

        with get_connection() as conn:
            weather_entry = get_latest_cache_entry(conn, "weather")
            iss_entry = get_latest_cache_entry(conn, "iss")
            trivia_entry = get_latest_cache_entry(conn, "trivia")
            news_entry = get_latest_cache_entry(conn, "news")
            ai_dev_entry = get_latest_cache_entry(conn, "ai_dev")
            entertainment_entry = get_latest_cache_entry(conn, "entertainment")

        if weather_entry is None:
            notes.append("No weather data cached.")
        else:
            weather_data = weather_entry["data"]
            forecast = weather_data.get("forecast_7d", {})
            dates = forecast.get("dates", [])
            max_temps = forecast.get("temperature_max_c", [])
            min_temps = forecast.get("temperature_min_c", [])
            today_high = max_temps[0] if max_temps else None
            today_low = min_temps[0] if min_temps else None
            weather_snapshot = {
                "location": weather_data.get("location"),
                "cached_at": weather_entry["fetched_at"],
                "current": weather_data.get("current"),
                "today": {
                    "date": dates[0] if dates else None,
                    "high_c": today_high,
                    "low_c": today_low,
                },
            }

        if iss_entry is None:
            notes.append("No ISS data cached.")
        else:
            iss_data = iss_entry["data"]
            distance_km = haversine_km(
                iss_data["latitude"],
                iss_data["longitude"],
                reference_lat,
                reference_lng,
            )
            iss_snapshot = {
                "latitude": iss_data["latitude"],
                "longitude": iss_data["longitude"],
                "cached_at": iss_entry["fetched_at"],
                "reference_point": {
                    "latitude": reference_lat,
                    "longitude": reference_lng,
                    "label": ISS_REFERENCE_LABEL,
                },
                "distance_km": round(distance_km, 2),
                "near_reference": distance_km <= near_threshold_km,
                "near_threshold_km": near_threshold_km,
            }

        if trivia_entry is None:
            notes.append("No trivia data cached.")
        else:
            questions = trivia_entry["data"].get("questions", [])
            if not questions:
                notes.append("Trivia cache is empty.")
            else:
                question = random.choice(questions)
                trivia_snapshot = {
                    "question": question.get("question"),
                    "category": question.get("category"),
                    "difficulty": question.get("difficulty"),
                    "cached_at": trivia_entry["fetched_at"],
                }

        news_snapshot = _headline_snapshot(news_entry, limit=3)
        if news_entry is None:
            notes.append("No world news cached.")
        ai_dev_snapshot = _headline_snapshot(ai_dev_entry, limit=3)
        if ai_dev_entry is None:
            notes.append("No AI developments cached.")
        entertainment_snapshot = _headline_snapshot(entertainment_entry, limit=3)
        if entertainment_entry is None:
            notes.append("No entertainment headlines cached.")

        return {
            "generated_at": now.isoformat(),
            "weather": weather_snapshot,
            "iss": iss_snapshot,
            "trivia": trivia_snapshot,
            "news": news_snapshot,
            "ai_dev": ai_dev_snapshot,
            "entertainment": entertainment_snapshot,
            "notes": notes,
        }

    def news_brief(self, limit: int = 5) -> dict:
        now = datetime.now(timezone.utc)
        notes: list[str] = []

        with get_connection() as conn:
            news_entry = get_latest_cache_entry(conn, "news")
            ai_dev_entry = get_latest_cache_entry(conn, "ai_dev")
            entertainment_entry = get_latest_cache_entry(conn, "entertainment")

        news = _headline_snapshot(news_entry, limit=limit)
        ai_dev = _headline_snapshot(ai_dev_entry, limit=limit)
        entertainment = _headline_snapshot(entertainment_entry, limit=limit)

        if news is None:
            notes.append("No world news cached.")
        if ai_dev is None:
            notes.append("No AI developments cached.")
        if entertainment is None:
            notes.append("No entertainment headlines cached.")

        return {
            "generated_at": now.isoformat(),
            "news": news,
            "ai_dev": ai_dev,
            "entertainment": entertainment,
            "notes": notes,
        }

    def cache_efficiency(self) -> dict:
        now = datetime.now(timezone.utc)
        sources_stats: list[dict] = []

        with get_connection() as conn:
            summaries = get_per_source_cache_summary(conn)
            summary_by_source = {row["source"]: row for row in summaries}

        for source, ttl_seconds in CACHE_TTL.items():
            summary = summary_by_source.get(source)
            if summary is None:
                sources_stats.append(
                    {
                        "source": source,
                        "entry_count": 0,
                        "last_fetched": None,
                        "age_seconds": None,
                        "ttl_seconds": ttl_seconds,
                        "is_stale": True,
                        "hit_friendly_status": "cold_miss",
                        "avg_fetch_duration_ms": None,
                    }
                )
                continue

            last_fetched = summary["last_fetched"]
            age_seconds: float | None = None
            is_stale = True
            hit_friendly_status = "stale_serves_fallback"

            if last_fetched:
                fetched_dt = parse_utc_iso(last_fetched)
                age_seconds = round((now - fetched_dt).total_seconds(), 1)
                is_stale = age_seconds > ttl_seconds

            latest_expires = summary.get("latest_expires_at")
            if latest_expires:
                expires_dt = parse_utc_iso(latest_expires)
                cache_valid = now <= expires_dt
                if cache_valid:
                    hit_friendly_status = "hit_friendly"
                elif summary["entry_count"] > 0:
                    hit_friendly_status = "stale_serves_fallback"
            elif summary["entry_count"] > 0:
                hit_friendly_status = "stale_serves_fallback"

            sources_stats.append(
                {
                    "source": source,
                    "entry_count": summary["entry_count"],
                    "last_fetched": last_fetched,
                    "age_seconds": age_seconds,
                    "ttl_seconds": ttl_seconds,
                    "is_stale": is_stale,
                    "hit_friendly_status": hit_friendly_status,
                    "avg_fetch_duration_ms": summary.get("avg_fetch_duration_ms"),
                }
            )

        hit_friendly_count = sum(
            1 for row in sources_stats if row["hit_friendly_status"] == "hit_friendly"
        )

        return {
            "generated_at": now.isoformat(),
            "sources": sources_stats,
            "summary": {
                "tracked_sources": len(CACHE_TTL),
                "hit_friendly_sources": hit_friendly_count,
                "overall_status": (
                    "optimal"
                    if hit_friendly_count == len(CACHE_TTL)
                    else "partial"
                    if hit_friendly_count > 0
                    else "cold"
                ),
            },
        }

    def health_summary(self) -> dict:
        with get_connection() as conn:
            stats = conn.execute(
                """
                SELECT source, COUNT(*) AS entries, MAX(fetched_at) AS last_fetched
                FROM cache_entries
                GROUP BY source
                """
            ).fetchall()

        sources = {
            row["source"]: {
                "cached_entries": row["entries"],
                "last_fetched": row["last_fetched"],
            }
            for row in stats
        }

        return {
            "status": "healthy",
            "source_count": len(sources),
            "sources": sources,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def cache_stats_snapshot(self) -> dict:
        return self.cache_efficiency()
