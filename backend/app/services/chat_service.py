"""Project-run conversational chat backed by Gemini."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bson import ObjectId

from app.core.config import Settings
from app.db.repositories.chat_message_repository import ChatMessageRepository
from app.db.repositories.finding_repository import FindingRepository
from app.db.repositories.memory_repository import MemoryRepository
from app.db.repositories.report_repository import ReportRepository
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.models.chat_message import ChatMessage, ChatRole
from app.models.run import Run
from app.schemas.chat import ChatMessageResponse, ChatSendResponse
from app.services.gemini_chat_client import GeminiChatClient, GeminiChatError
from app.services.gemini_credential_service import GeminiCredentialService
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.workspace.artifact_reader import (
    WorkspaceArtifactAccessError,
    WorkspaceArtifactNotFoundError,
    read_workspace_text_file,
)

_MAX_CONTEXT_CHARS = 24_000
_MAX_HISTORY_MESSAGES = 40
_MAX_FINDINGS_IN_CONTEXT = 40
_MAX_REPORT_MARKDOWN_CHARS = 8_000


class ChatService:
    """Run-scoped chat: loads project/run context and calls Gemini."""

    def __init__(
        self,
        *,
        settings: Settings,
        run_repository: RunRepository,
        run_service: RunService,
        project_service: ProjectService,
        chat_message_repository: ChatMessageRepository,
        finding_repository: FindingRepository,
        memory_repository: MemoryRepository,
        report_repository: ReportRepository,
        gemini_client: GeminiChatClient | None = None,
        gemini_credential_service: GeminiCredentialService | None = None,
    ) -> None:
        self._settings = settings
        self._run_repository = run_repository
        self._run_service = run_service
        self._project_service = project_service
        self._chat_message_repository = chat_message_repository
        self._finding_repository = finding_repository
        self._memory_repository = memory_repository
        self._report_repository = report_repository
        self._gemini_client = gemini_client or GeminiChatClient(settings)
        self._gemini_credential_service = gemini_credential_service

    def list_messages(self, user_id: str, run_id: str) -> list[ChatMessageResponse]:
        self._require_run(user_id, run_id)
        messages = self._chat_message_repository.list_by_run(run_id, user_id)
        return [self._to_response(message) for message in messages]

    def clear_messages(self, user_id: str, run_id: str) -> int:
        self._require_run(user_id, run_id)
        return self._chat_message_repository.delete_by_run(run_id, user_id)

    def send_message(self, user_id: str, run_id: str, content: str) -> ChatSendResponse:
        run = self._require_run(user_id, run_id)
        project = self._project_service.get_project(user_id, run.project_id)

        history = self._chat_message_repository.list_by_run(
            run_id,
            user_id,
            limit=_MAX_HISTORY_MESSAGES,
        )
        system_instruction = self._build_system_instruction(
            run=run,
            project_name=project.name,
            user_id=user_id,
        )

        try:
            api_key = (
                self._gemini_credential_service.try_get_api_key(user_id)
                if self._gemini_credential_service is not None
                else None
            )
            assistant_text = self._gemini_client.generate_reply(
                system_instruction=system_instruction,
                history=history,
                user_message=content.strip(),
                api_key=api_key,
            )
        except GeminiChatError:
            raise

        user_message = self._chat_message_repository.add(
            message_id=str(ObjectId()),
            run_id=run.id,
            project_id=run.project_id,
            user_id=user_id,
            role=ChatRole.USER,
            content=content.strip(),
        )
        assistant_message = self._chat_message_repository.add(
            message_id=str(ObjectId()),
            run_id=run.id,
            project_id=run.project_id,
            user_id=user_id,
            role=ChatRole.ASSISTANT,
            content=assistant_text,
        )

        return ChatSendResponse(
            user_message=self._to_response(user_message),
            assistant_message=self._to_response(assistant_message),
        )

    def _require_run(self, user_id: str, run_id: str) -> Run:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)
        return run

    def _build_system_instruction(self, *, run: Run, project_name: str, user_id: str) -> str:
        context = self._build_run_context(run=run, project_name=project_name, user_id=user_id)
        return (
            "You are theReCode Chat, an assistant for a single autonomous engineering run.\n"
            "Answer using the provided run context and conversation history.\n"
            "When discussing findings, cite file:line and tool (e.g. ruff, pytest).\n"
            "Prefer actionable fixes for code-quality and test errors.\n"
            "If something is not in the context, say you do not have that information.\n"
            "Be concise, technical, and actionable.\n\n"
            f"=== RUN CONTEXT ===\n{context}\n=== END CONTEXT ==="
        )

    def _build_run_context(self, *, run: Run, project_name: str, user_id: str) -> str:
        findings = self._finding_repository.list_by_run(run.id)[:_MAX_FINDINGS_IN_CONTEXT]
        memories = self._memory_repository.list_by_project(run.project_id)[:20]
        report = self._report_repository.get_by_run(run.id)

        finding_summaries = [
            {
                "severity": finding.severity,
                "message": finding.message,
                "agent": finding.agent,
                "tool": finding.tool,
                "category": finding.category,
                "location": self._format_location(finding.file, finding.line_start),
                "status": finding.status,
            }
            for finding in findings
        ]
        memory_summaries = [
            {
                "type": memory.memory_type,
                "title": memory.title,
                "content": memory.content[:400],
            }
            for memory in memories
        ]

        intelligence: dict[str, Any] | None = None
        if run.project_intelligence is not None:
            intelligence = run.project_intelligence.model_dump(mode="json")

        report_markdown = self._safe_report_markdown(user_id=user_id, run_id=run.id, report=report)

        payload = {
            "project_name": project_name,
            "project_id": run.project_id,
            "run_id": run.id,
            "run_status": run.status,
            "repository_id": run.repository_id,
            "project_intelligence": intelligence,
            "findings_count": len(findings),
            "findings": finding_summaries,
            "memories": memory_summaries,
            "report": None
            if report is None
            else {
                "status": report.status,
                "final_health_score": report.final_health_score,
                "pull_request_url": report.pull_request_url,
                "branch_name": report.branch_name,
                "markdown_path": report.markdown_path,
                "pdf_path": report.pdf_path,
            },
            "report_markdown_excerpt": report_markdown,
        }
        text = json.dumps(payload, default=str, indent=2)
        if len(text) > _MAX_CONTEXT_CHARS:
            return text[:_MAX_CONTEXT_CHARS] + "\n...[truncated]"
        return text

    def _safe_report_markdown(self, *, user_id: str, run_id: str, report: Any) -> str | None:
        if report is None or not getattr(report, "markdown_path", None):
            return None
        try:
            workspace = self._run_service.get_workspace_for_run(user_id, run_id)
            markdown = read_workspace_text_file(workspace.root, report.markdown_path)
        except (
            WorkspaceArtifactNotFoundError,
            WorkspaceArtifactAccessError,
            FileNotFoundError,
            OSError,
            RunNotFoundError,
        ):
            return None
        markdown = markdown.strip()
        if not markdown:
            return None
        if len(markdown) > _MAX_REPORT_MARKDOWN_CHARS:
            return markdown[:_MAX_REPORT_MARKDOWN_CHARS] + "\n...[truncated]"
        return markdown

    @staticmethod
    def _format_location(file: str | None, line_start: int | None) -> str | None:
        if not file:
            return None
        name = Path(file.replace("\\", "/")).name
        if line_start is not None:
            return f"{name}:{line_start}"
        return name

    @staticmethod
    def _to_response(message: ChatMessage) -> ChatMessageResponse:
        return ChatMessageResponse(
            id=message.id,
            run_id=message.run_id,
            project_id=message.project_id,
            role=message.role.value,
            content=message.content,
            created_at=message.created_at,
        )
