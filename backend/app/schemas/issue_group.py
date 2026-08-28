from datetime import datetime

from pydantic import BaseModel, Field

from app.models.issue_group import IssueGroup


class IssueGroupResponse(IssueGroup):
    """API response for a correlated issue group."""


class IssueCorrelationResponse(BaseModel):
    run_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    issue_groups: list[IssueGroupResponse]
    issue_group_count: int
    finding_count: int
    duplicate_count: int = Field(ge=0)
