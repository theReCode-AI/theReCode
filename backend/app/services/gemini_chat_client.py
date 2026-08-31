"""Direct Gemini API client for multi-turn project-run chat."""

from __future__ import annotations

from google import genai
from google.genai import types

from app.core.config import Settings
from app.google_adk.bootstrap import (
    GoogleAdkConfigurationError,
    bootstrap_google_genai,
    ensure_google_adk_configured,
)
from app.models.chat_message import ChatMessage, ChatRole


class GeminiChatError(RuntimeError):
    """Raised when Gemini chat generation fails."""


class GeminiChatClient:
    """Thin wrapper around google-genai for conversational turns."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def generate_reply(
        self,
        *,
        system_instruction: str,
        history: list[ChatMessage],
        user_message: str,
        api_key: str | None = None,
    ) -> str:
        bootstrap_google_genai(self._settings, api_key=api_key)
        try:
            ensure_google_adk_configured(self._settings, api_key=api_key)
        except GoogleAdkConfigurationError as exc:
            raise GeminiChatError(str(exc)) from exc

        resolved_key = (api_key or "").strip() or None
        if resolved_key is None:
            from app.google_adk.bootstrap import resolve_api_key

            resolved_key = resolve_api_key(self._settings) or None
        client = genai.Client(api_key=resolved_key)
        contents = self._build_contents(history, user_message)

        try:
            response = client.models.generate_content(
                model=self._settings.gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.4,
                    # Chat must not enter tool/AFC loops — that hangs multi-turn replies.
                    tools=[],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True,
                    ),
                    tool_config=types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(
                            mode=types.FunctionCallingConfigMode.NONE,
                        ),
                    ),
                ),
            )
        except Exception as exc:  # noqa: BLE001 — surface provider errors to API layer
            raise GeminiChatError(f"Gemini chat failed: {exc}") from exc

        text = self._extract_text(response)
        if not text:
            raise GeminiChatError("Gemini returned an empty response.")
        return text

    @staticmethod
    def _extract_text(response: object) -> str:
        direct = (getattr(response, "text", None) or "").strip()
        if direct:
            return direct

        # Fallback when .text is empty but candidates still have parts.
        candidates = getattr(response, "candidates", None) or []
        chunks: list[str] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    chunks.append(part_text)
        return "\n".join(chunks).strip()

    @staticmethod
    def _build_contents(history: list[ChatMessage], user_message: str) -> list[types.Content]:
        contents: list[types.Content] = []
        for message in history:
            role = "user" if message.role == ChatRole.USER else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=message.content)],
                ),
            )
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(text=user_message)],
            ),
        )
        return contents
