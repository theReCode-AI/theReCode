"""LLM-backed file rewriter for semantic (non-lint) patch plans."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from google import genai
from google.genai import types

from app.core.config import Settings
from app.google_adk.bootstrap import (
    GoogleAdkConfigurationError,
    bootstrap_google_genai,
    ensure_google_adk_configured,
)
from app.models.patch_plan import PatchPlan


class CodeRewriteError(RuntimeError):
    """Raised when an LLM code rewrite fails."""


class CodeRewriter(Protocol):
    def rewrite_files(self, patch_plan: PatchPlan, working_root: Path) -> list[str]:
        """Rewrite in-scope files for the plan. Returns relative paths that changed."""


@dataclass(frozen=True)
class _FileRewrite:
    path: str
    content: str


class GeminiCodeRewriter:
    """Ask Gemini to rewrite affected files according to a patch plan."""

    def __init__(self, settings: Settings, *, api_key: str | None = None) -> None:
        self._settings = settings
        self._api_key = (api_key or "").strip() or None

    def rewrite_files(self, patch_plan: PatchPlan, working_root: Path) -> list[str]:
        files = [
            path
            for path in patch_plan.affected_files
            if path and path != "repository"
        ]
        if not files:
            raise CodeRewriteError("Patch plan has no file-scoped targets to rewrite")

        file_payload: list[dict[str, str]] = []
        for relative_path in files:
            absolute = working_root / relative_path
            if not absolute.is_file():
                raise CodeRewriteError(f"Target file does not exist: {relative_path}")
            file_payload.append(
                {
                    "path": relative_path,
                    "content": absolute.read_text(encoding="utf-8"),
                },
            )

        bootstrap_google_genai(self._settings, api_key=self._api_key)
        try:
            ensure_google_adk_configured(self._settings, api_key=self._api_key)
        except GoogleAdkConfigurationError as exc:
            raise CodeRewriteError(str(exc)) from exc

        from app.google_adk.bootstrap import resolve_api_key

        api_key = self._api_key or resolve_api_key(self._settings) or None
        client = genai.Client(api_key=api_key)
        prompt = self._build_prompt(patch_plan, file_payload)

        try:
            response = client.models.generate_content(
                model=self._settings.gemini_model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text=prompt)],
                    ),
                ],
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "You are a senior Python engineer applying a scoped remediation. "
                        "Return ONLY valid JSON. Do not wrap it in markdown. "
                        "Preserve unrelated code. Only change what the plan requires."
                    ),
                    temperature=0.1,
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
        except Exception as exc:  # noqa: BLE001
            raise CodeRewriteError(f"Gemini rewrite failed: {exc}") from exc

        text = _extract_text(response)
        rewrites = _parse_rewrites(text, allowed_paths=set(files))
        if not rewrites:
            raise CodeRewriteError("Gemini returned no in-scope file rewrites")

        changed: list[str] = []
        for rewrite in rewrites:
            target = working_root / rewrite.path
            before = target.read_text(encoding="utf-8") if target.is_file() else ""
            if before == rewrite.content:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rewrite.content, encoding="utf-8")
            changed.append(rewrite.path)

        if not changed:
            raise CodeRewriteError(
                "Gemini rewrite produced no file content changes for this plan",
            )
        return changed

    @staticmethod
    def _build_prompt(patch_plan: PatchPlan, files: list[dict[str, str]]) -> str:
        modifications = [
            {
                "file": item.file,
                "description": item.description,
                "change_type": item.change_type,
            }
            for item in patch_plan.expected_modifications
        ]
        payload = {
            "title": patch_plan.title,
            "root_cause": patch_plan.root_cause,
            "solution_rationale": patch_plan.solution_rationale,
            "affected_files": patch_plan.affected_files,
            "expected_modifications": modifications,
            "files": files,
            "response_schema": {
                "files": [
                    {"path": "relative/path.py", "content": "full updated file contents"},
                ],
            },
        }
        return (
            "Apply the remediation plan to the provided files.\n"
            "Return JSON shaped as {\"files\":[{\"path\":\"...\",\"content\":\"...\"}]}.\n"
            "Only include files listed in affected_files.\n"
            "Each content value must be the complete updated file.\n\n"
            f"{json.dumps(payload, indent=2)}"
        )


def _extract_text(response: object) -> str:
    direct = (getattr(response, "text", None) or "").strip()
    if direct:
        return direct

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


def _parse_rewrites(text: str, *, allowed_paths: set[str]) -> list[_FileRewrite]:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise CodeRewriteError(f"Gemini rewrite response was not valid JSON: {exc}") from exc

    raw_files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(raw_files, list):
        raise CodeRewriteError("Gemini rewrite JSON must contain a files array")

    rewrites: list[_FileRewrite] = []
    for item in raw_files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        content = item.get("content")
        if path not in allowed_paths or not isinstance(content, str):
            continue
        rewrites.append(_FileRewrite(path=path, content=content))
    return rewrites
