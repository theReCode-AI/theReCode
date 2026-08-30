from datetime import datetime

from pydantic import BaseModel, Field

from app.models.memory_entry import MemoryEntry


class MemoryEntryResponse(MemoryEntry):
    """API response for a persisted memory entry."""


class CaptureRunMemoryResponse(BaseModel):
    run_id: str
    project_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    memories: list[MemoryEntryResponse]
    memory_count: int = Field(ge=0)
    project_memory_count: int = Field(ge=0)
    decision_memory_count: int = Field(ge=0)
    failure_memory_count: int = Field(ge=0)
    success_memory_count: int = Field(ge=0)


class PlanningMemoryResponse(BaseModel):
    run_id: str
    memory_count: int = Field(ge=0)
    snippets: list[str] = Field(default_factory=list)
