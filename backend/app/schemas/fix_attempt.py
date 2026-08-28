from datetime import datetime

from pydantic import BaseModel, Field

from app.models.fix_attempt import FixAttempt


class FixAttemptResponse(FixAttempt):
    """API response for a persisted fix attempt."""


class FixAttemptDiffResponse(BaseModel):
    fix_attempt_id: str
    run_id: str
    diff_path: str
    content: str
    changed_files: list[str] = Field(default_factory=list)


class CodeFixResponse(BaseModel):
    run_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    fix_attempts: list[FixAttemptResponse]
    attempt_count: int = Field(ge=0)
    applied_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    rolled_back_count: int = Field(ge=0)
    run_status: str
