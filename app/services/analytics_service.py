from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from app.db.database import get_connection, get_iss_position_history
from app.utils.geo import haversine_km


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
