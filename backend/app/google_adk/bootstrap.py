"""Configure Google GenAI / ADK for Gemini API (not Vertex AI)."""

from __future__ import annotations

import os

from app.core.config import Settings


class GoogleAdkConfigurationError(RuntimeError):
    """Raised when Google ADK / Gemini API credentials are missing or invalid."""


def ensure_google_adk_configured(
    settings: Settings,
    *,
    api_key: str | None = None,
) -> None:
    """Validate that a Gemini API key is available for ADK runs."""
    resolved = (api_key or resolve_api_key(settings)).strip()
    if not resolved:
        raise GoogleAdkConfigurationError(
            "Gemini API key is required. Add your key under Settings, or set "
            "THERECODE_GOOGLE_API_KEY / GOOGLE_API_KEY in backend/app/.env "
            "(get a key from https://aistudio.google.com/apikey).",
        )


def bootstrap_google_genai(
    settings: Settings,
    *,
    api_key: str | None = None,
) -> None:
    """Apply environment variables consumed by google-adk and google-genai."""
    resolved = (api_key or resolve_api_key(settings)).strip()
    if resolved:
        os.environ["GOOGLE_API_KEY"] = resolved

    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = (
        "TRUE" if settings.google_genai_use_vertexai else "FALSE"
    )


def resolve_api_key(settings: Settings) -> str:
    return (settings.google_api_key or os.environ.get("GOOGLE_API_KEY", "")).strip()
