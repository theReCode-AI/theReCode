"""Configure Google GenAI / ADK for Gemini API (not Vertex AI)."""

from __future__ import annotations

import os

from app.core.config import Settings


class GoogleAdkConfigurationError(RuntimeError):
    """Raised when Google ADK / Gemini API credentials are missing or invalid."""


def ensure_google_adk_configured(settings: Settings) -> None:
    """Validate that a Gemini API key is available for ADK runs."""
    api_key = _resolve_api_key(settings)
    if not api_key:
        raise GoogleAdkConfigurationError(
            "Gemini API key is required. Set CODETHERA_GOOGLE_API_KEY or GOOGLE_API_KEY "
            "in backend/app/.env (get a key from https://aistudio.google.com/apikey).",
        )


def bootstrap_google_genai(settings: Settings) -> None:
    """Apply environment variables consumed by google-adk and google-genai."""
    api_key = _resolve_api_key(settings)
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key

    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = (
        "TRUE" if settings.google_genai_use_vertexai else "FALSE"
    )


def _resolve_api_key(settings: Settings) -> str:
    return (settings.google_api_key or os.environ.get("GOOGLE_API_KEY", "")).strip()
