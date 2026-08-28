from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.repository import GitProvider


class GitCredential(BaseModel):
    """Encrypted Git provider credential for a user."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    user_id: str
    provider: GitProvider
    encrypted_token: str
    token_label: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "GitCredential":
        document = document.copy()
        document["_id"] = str(document["_id"])
        document["user_id"] = str(document["user_id"])
        return cls.model_validate(document)
