from datetime import UTC, datetime

from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.chat_message import ChatMessage, ChatRole


class ChatMessageRepository(BaseRepository):
    """Repository for run-scoped Gemini chat messages."""

    collection_name = collections.CHAT_MESSAGES

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
        now = datetime.now(UTC)
        document = {
            "_id": ObjectId(message_id),
            "run_id": ObjectId(run_id),
            "project_id": ObjectId(project_id),
            "user_id": ObjectId(user_id),
            "role": role.value,
            "content": content,
            "created_at": now,
        }
        self.collection.insert_one(document)
        return ChatMessage.from_document(document)

    def list_by_run(self, run_id: str, user_id: str, *, limit: int = 200) -> list[ChatMessage]:
        documents = (
            self.collection.find(
                {"run_id": ObjectId(run_id), "user_id": ObjectId(user_id)},
            )
            .sort("created_at", 1)
            .limit(limit)
        )
        return [ChatMessage.from_document(document) for document in documents]

    def delete_by_run(self, run_id: str, user_id: str) -> int:
        result = self.collection.delete_many(
            {"run_id": ObjectId(run_id), "user_id": ObjectId(user_id)},
        )
        return int(result.deleted_count)
