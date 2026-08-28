from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Project(BaseModel):
    """User-owned project."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    user_id: str
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "Project":
        document = document.copy()
        document["_id"] = str(document["_id"])
        document["user_id"] = str(document["user_id"])
        return cls.model_validate(document)
