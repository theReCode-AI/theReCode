from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GitProvider = Literal["github", "gitlab"]


class Repository(BaseModel):
    """Git repository linked to a project."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    project_id: str
    provider: GitProvider
    full_name: str
    default_branch: str = "main"
    clone_url: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "Repository":
        document = document.copy()
        document["_id"] = str(document["_id"])
        document["project_id"] = str(document["project_id"])
        return cls.model_validate(document)
