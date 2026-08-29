from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    """Persisted chat turn for a project run conversation."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    run_id: str
    project_id: str
    user_id: str
    role: ChatRole
    content: str
    created_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "ChatMessage":
        document = document.copy()
        document["_id"] = str(document["_id"])
        document["run_id"] = str(document["run_id"])
        document["project_id"] = str(document["project_id"])
        document["user_id"] = str(document["user_id"])
        return cls.model_validate(document)
