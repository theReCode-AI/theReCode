from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class OrchestrationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RunAgentState(BaseModel):
    """Persisted orchestration state for an autonomous run."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    run_id: str
    status: OrchestrationStatus = OrchestrationStatus.PENDING
    current_stage: str | None = None
    current_agent: str | None = None
    iteration: int = 1
    progress: int = Field(default=0, ge=0, le=100)
    approval_required: bool = False
    completed_stages: list[str] = Field(default_factory=list)
    completed_agents: list[str] = Field(default_factory=list)
    error_message: str | None = None
    updated_at: datetime
    created_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "RunAgentState":
        document = document.copy()
        document["_id"] = str(document["_id"])
        document["run_id"] = str(document["run_id"])
        return cls.model_validate(document)
