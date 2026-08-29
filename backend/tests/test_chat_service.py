from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from bson import ObjectId

from app.core.config import Settings
from app.models.chat_message import ChatMessage, ChatRole
from app.models.run import Run, RunStatus
from app.schemas.project import ProjectResponse
from app.services.chat_service import ChatService
from app.services.gemini_chat_client import GeminiChatClient


class FakeChatMessageRepository:
    def __init__(self) -> None:
        self._messages: list[ChatMessage] = []

    def list_by_run(self, run_id: str, user_id: str, *, limit: int = 200) -> list[ChatMessage]:
        return [
            message
            for message in self._messages
            if message.run_id == run_id and message.user_id == user_id
        ][:limit]

    def add(
        self,
        *,
        message_id: str,
        run_id: str,
        project_id: str,
        user_id: str,
        role: ChatRole,
        content: str,
    ) -> ChatMessage:
        message = ChatMessage(
            _id=message_id,
            run_id=run_id,
            project_id=project_id,
            user_id=user_id,
            role=role,
            content=content,
            created_at=datetime.now(UTC),
        )
        self._messages.append(message)
        return message

    def delete_by_run(self, run_id: str, user_id: str) -> int:
        before = len(self._messages)
        self._messages = [
            message
            for message in self._messages
            if not (message.run_id == run_id and message.user_id == user_id)
        ]
        return before - len(self._messages)


@pytest.fixture
def chat_service() -> ChatService:
    run_id = str(ObjectId())
    project_id = str(ObjectId())
    user_id = str(ObjectId())
    now = datetime.now(UTC)

    run = Run(
        _id=run_id,
        project_id=project_id,
        user_id=user_id,
        repository_id=None,
        status=RunStatus.COMPLETED,
        workspace_path="/tmp/workspace",
        created_at=now,
        updated_at=now,
    )

    run_repository = MagicMock()
    run_repository.get_by_id_for_user.return_value = run

    project_service = MagicMock()
    project_service.get_project.return_value = ProjectResponse(
        id=project_id,
        user_id=user_id,
        name="Demo Project",
        description=None,
        created_at=now,
        updated_at=now,
    )

    finding_repository = MagicMock()
    finding_repository.list_by_run.return_value = []
    memory_repository = MagicMock()
    memory_repository.list_by_project.return_value = []
    report_repository = MagicMock()
    report_repository.get_by_run.return_value = None

    gemini = MagicMock(spec=GeminiChatClient)
    gemini.generate_reply.return_value = "This run completed successfully."

    service = ChatService(
        settings=Settings(google_api_key="test-key", gemini_model="gemini-2.5-flash"),
        run_repository=run_repository,
        project_service=project_service,
        chat_message_repository=FakeChatMessageRepository(),  # type: ignore[arg-type]
        finding_repository=finding_repository,
        memory_repository=memory_repository,
        report_repository=report_repository,
        gemini_client=gemini,
    )
    service._test_ids = (user_id, run_id, gemini)  # type: ignore[attr-defined]
    return service


def test_send_message_persists_user_and_assistant_turns(chat_service: ChatService) -> None:
    user_id, run_id, gemini = chat_service._test_ids  # type: ignore[attr-defined]

    response = chat_service.send_message(user_id, run_id, "What is the status?")

    assert response.user_message.content == "What is the status?"
    assert response.assistant_message.content == "This run completed successfully."
    gemini.generate_reply.assert_called_once()
    messages = chat_service.list_messages(user_id, run_id)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"
