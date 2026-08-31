from datetime import datetime

from pydantic import BaseModel, Field

from app.models.git_operation import GitOperation


class GitOperationResponse(GitOperation):
    """API response for a persisted git operation."""


class RunGitFinalizationResponse(BaseModel):
    run_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    operation: GitOperationResponse
    run_status: str


class GitFinalizationRequest(BaseModel):
    base_branch: str | None = Field(default=None, min_length=1, max_length=200)
    force: bool = False
