"""Tests for Google ADK bootstrap and configuration."""

import os

import pytest

from app.core.config import Settings
from app.google_adk.bootstrap import (
    GoogleAdkConfigurationError,
    bootstrap_google_genai,
    ensure_google_adk_configured,
)


def test_bootstrap_sets_gemini_api_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)

    settings = Settings(
        google_api_key="test-gemini-key",
        google_genai_use_vertexai=False,
    )
    bootstrap_google_genai(settings)

    assert os.environ["GOOGLE_API_KEY"] == "test-gemini-key"
    assert os.environ["GOOGLE_GENAI_USE_VERTEXAI"] == "FALSE"


def test_ensure_google_adk_configured_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    settings = Settings(google_api_key="")
    with pytest.raises(GoogleAdkConfigurationError):
        ensure_google_adk_configured(settings)
