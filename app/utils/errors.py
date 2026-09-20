from __future__ import annotations

import httpx


def friendly_http_status_error(exc: httpx.HTTPStatusError) -> str:
    """Turn upstream HTTP failures into dashboard-safe messages."""
    status = exc.response.status_code
    url = str(exc.request.url).lower()

    if status == 429:
        if "open-meteo" in url:
            return (
                "Open-Meteo is rate-limiting this server. "
                "Cached weather is shown when available; optional IMD or OpenWeather keys improve reliability."
            )
        return "The external service is temporarily busy. Please try again in a few minutes."

    if status == 401:
        if "imd.gov.in" in url:
            return "IMD rejected the API key. Check IMD_API_KEY on the server."
        if "openweathermap" in url:
            return "OpenWeatherMap rejected the API key. Check OPENWEATHER_API_KEY on the server."
        if "anthropic" in url:
            return "Anthropic rejected the API key. Check ANTHROPIC_API_KEY on the server."
        return "The upstream service rejected our credentials. Check server API keys."

    if status == 404:
        if "anthropic" in url:
            return (
                "Anthropic could not find the configured model. "
                "The server model ID may need updating."
            )
        return "The requested upstream resource was not found."

    if status >= 500:
        return "A weather data provider is having trouble right now. Please try again shortly."

    return f"The external service returned an error (HTTP {status}). Please try again."


def friendly_http_error(exc: httpx.HTTPError) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return friendly_http_status_error(exc)
    if isinstance(exc, httpx.TimeoutException):
        return "The request timed out while waiting for an external service."
    if isinstance(exc, httpx.ConnectError):
        return "Could not reach an external service. Check your network or try again later."
    return "An external service request failed. Please try again shortly."
