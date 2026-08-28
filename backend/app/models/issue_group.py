from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.finding_enums import DiagnosticAgentName, FindingSeverity
from app.models.issue_group_enums import IssueGroupStatus


class IssueGroup(BaseModel):
    """Correlated group of related findings representing a single actionable issue."""

    model_config = ConfigDict(populate_by_name=True)

    issue_group_id: str
    run_id: str
    title: str
    summary: str
    root_cause: str
    finding_ids: list[str]
    categories: list[str]
    agents: list[DiagnosticAgentName]
    tools: list[str]
    severity: FindingSeverity
    priority_score: float = Field(ge=0.0, le=100.0)
    priority_rank: int = Field(ge=1)
    affected_files: list[str]
    duplicate_count: int = Field(default=0, ge=0)
    related_count: int = Field(default=0, ge=0)
    status: IssueGroupStatus = IssueGroupStatus.OPEN
    created_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "IssueGroup":
        document = document.copy()
        document["issue_group_id"] = str(document.pop("_id"))
        document["run_id"] = str(document["run_id"])
        return cls.model_validate(document)
