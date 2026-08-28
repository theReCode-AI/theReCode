from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.memory_enums import MemoryType


class MemoryEntry(BaseModel):
    """Persisted project memory captured from autonomous runs."""

    model_config = ConfigDict(populate_by_name=True)

    memory_id: str
    project_id: str
    run_id: str
    memory_type: MemoryType
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_key: str
    artifact_path: str | None = None
    created_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "MemoryEntry":
        document = document.copy()
        document["memory_id"] = str(document.pop("_id"))
        document["project_id"] = str(document["project_id"])
        document["run_id"] = str(document["run_id"])
        return cls.model_validate(document)
