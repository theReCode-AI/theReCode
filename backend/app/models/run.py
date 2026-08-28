from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models.project_intelligence import ProjectIntelligence


class RunStatus(StrEnum):
    CREATED = "CREATED"
    CLONING = "CLONING"
    ANALYZING = "ANALYZING"
    DIAGNOSING = "DIAGNOSING"
    PLANNING = "PLANNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    FIXING = "FIXING"
    VERIFYING = "VERIFYING"
    SELF_CORRECTING = "SELF_CORRECTING"
    PEER_REVIEW = "PEER_REVIEW"
    FINAL_REVIEW = "FINAL_REVIEW"
    PUSHING = "PUSHING"
    REPORTING = "REPORTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Run(BaseModel):
    """Autonomous run persisted in MongoDB."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    project_id: str
    user_id: str
    repository_id: str | None = None
    status: RunStatus = RunStatus.CREATED
    workspace_path: str
    project_intelligence: ProjectIntelligence | None = None
    analyzed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "Run":
        document = document.copy()
        document["_id"] = str(document["_id"])
        document["project_id"] = str(document["project_id"])
        document["user_id"] = str(document["user_id"])
        if document.get("repository_id") is not None:
            document["repository_id"] = str(document["repository_id"])
        return cls.model_validate(document)
