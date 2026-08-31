from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GeminiCredential(BaseModel):
    """Encrypted Gemini API key for a user."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    user_id: str
    encrypted_api_key: str
    key_label: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "GeminiCredential":
        document = document.copy()
        document["_id"] = str(document["_id"])
        document["user_id"] = str(document["user_id"])
        return cls.model_validate(document)
