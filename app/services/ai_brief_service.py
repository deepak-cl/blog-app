from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import DEFAULT_WEATHER_LOCATION
from app.services.analytics_service import AnalyticsService
from app.services.weather_service import WeatherService
from app.utils.geo import format_coords_label

PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "openai": {
        "env_vars": ("OPENAI_API_KEY",),
        "model": "gpt-4o-mini",
        "label": "OpenAI",
    },
    "anthropic": {
        "env_vars": ("ANTHROPIC_API_KEY",),
        "model": "claude-haiku-4-5",
        "label": "Anthropic",
    },
    "gemini": {
        "env_vars": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "model": "gemini-2.5-flash-lite",
        "label": "Gemini",
    },
}


class AIBriefNotConfiguredError(Exception):
    """Raised when no AI provider keys are available on the server."""


class AIBriefService:
    def __init__(self) -> None:
        self._analytics = AnalyticsService()

    @staticmethod
    def _resolve_api_key(provider: str) -> str | None:
        for env_var in PROVIDER_CONFIG[provider]["env_vars"]:
            key = os.environ.get(env_var, "").strip()
            if key:
                return key
        return None

    def configured_providers(self) -> list[dict[str, str]]:
        return [
            {
                "id": provider_id,
                "label": PROVIDER_CONFIG[provider_id]["label"],
                "model": PROVIDER_CONFIG[provider_id]["model"],
            }
            for provider_id in PROVIDER_CONFIG
            if self._resolve_api_key(provider_id)
        ]

    def _build_prompt(self, brief: dict, *, location_label: str | None = None) -> str:
        weather = brief.get("weather") or {}
        iss = brief.get("iss") or {}
        trivia = brief.get("trivia") or {}
        resolved_location = weather.get("location") or location_label or DEFAULT_WEATHER_LOCATION

        facts: list[str] = [
            f"Location: {resolved_location}",
        ]

        if weather:
            current = weather.get("current") or {}
            today = weather.get("today") or {}
            facts.append(
                "Weather: "
                f"{current.get('condition', 'unknown')}, "
                f"{current.get('temperature_c')}°C now; "
                f"today high {today.get('high_c')}°C / low {today.get('low_c')}°C."
            )
        else:
            facts.append("Weather: not cached.")

        if iss:
            ref = iss.get("reference_point") or {}
            facts.append(
                "ISS: "
                f"lat {iss.get('latitude')}, lng {iss.get('longitude')}; "
                f"{iss.get('distance_km')} km from {ref.get('label', 'reference')}; "
                f"{'near' if iss.get('near_reference') else 'far from'} reference point."
            )
        else:
            facts.append("ISS: not cached.")

        if trivia:
            facts.append(
                "Trivia: "
                f"\"{trivia.get('question')}\" "
                f"({trivia.get('category')}, {trivia.get('difficulty')})."
            )
        else:
            facts.append("Trivia: not cached.")

        if brief.get("notes"):
            facts.append("Notes: " + " ".join(brief["notes"]))

        return (
            f"Write a friendly 2-3 sentence daily brief for someone in "
            f"{resolved_location}. Use only these facts:\n\n"
            + "\n".join(f"- {line}" for line in facts)
            + "\n\nKeep it warm, concise, and practical. Do not invent details."
        )

    async def _call_openai(self, api_key: str, prompt: str, model: str) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.7,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

    async def _call_anthropic(self, api_key: str, prompt: str, model: str) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 150,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"].strip()

    async def _call_gemini(self, api_key: str, prompt: str, model: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                params={"key": api_key},
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": 150,
                        "temperature": 0.7,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    async def generate(
        self,
        provider: str | None = None,
        *,
        coords: tuple[float, float] | None = None,
    ) -> dict[str, Any]:
        configured = self.configured_providers()
        if not configured:
            raise AIBriefNotConfiguredError(
                "No AI provider API keys configured. Set OPENAI_API_KEY, "
                "ANTHROPIC_API_KEY, or GEMINI_API_KEY (or GOOGLE_API_KEY) on the server."
            )

        provider_id = (provider or configured[0]["id"]).lower()
        if provider_id not in PROVIDER_CONFIG:
            raise ValueError(
                f"Unknown provider '{provider_id}'. "
                f"Choose from: {', '.join(PROVIDER_CONFIG)}."
            )

        api_key = self._resolve_api_key(provider_id)
        if not api_key:
            raise AIBriefNotConfiguredError(
                f"No API key configured for provider '{provider_id}'. "
                f"Set one of: {', '.join(PROVIDER_CONFIG[provider_id]['env_vars'])}."
            )

        brief_kwargs: dict = {}
        location_label = DEFAULT_WEATHER_LOCATION
        if coords is not None:
            ref_lat, ref_lng = coords
            location_label = format_coords_label(ref_lat, ref_lng)
            brief_kwargs = {
                "reference_lat": ref_lat,
                "reference_lng": ref_lng,
                "reference_label": location_label,
            }
            weather_service = WeatherService(
                latitude=ref_lat,
                longitude=ref_lng,
                location_label=location_label,
            )
            await weather_service.get_or_refresh(force=False)

        brief = self._analytics.daily_brief(**brief_kwargs)
        prompt = self._build_prompt(brief, location_label=location_label)
        model = PROVIDER_CONFIG[provider_id]["model"]

        if provider_id == "openai":
            text = await self._call_openai(api_key, prompt, model)
        elif provider_id == "anthropic":
            text = await self._call_anthropic(api_key, prompt, model)
        else:
            text = await self._call_gemini(api_key, prompt, model)

        return {
            "provider": provider_id,
            "model": model,
            "location": location_label,
            "brief": text,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
