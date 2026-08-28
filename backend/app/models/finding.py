from datetime import datetime

from pydantic import BaseModel, Field

from app.models.finding_enums import (
    DiagnosticAgentName,
    FindingFixability,
    FindingSeverity,
    FindingStatus,
)


class Finding(BaseModel):
    """Normalized diagnostic finding shared across all scanner agents."""

    finding_id: str
    run_id: str
    agent: DiagnosticAgentName
    tool: str
    category: str
    severity: FindingSeverity
    confidence: float = Field(ge=0.0, le=1.0)
    file: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    message: str
    rule_id: str | None = None
    evidence: str | None = None
    fixability: FindingFixability = FindingFixability.UNKNOWN
    status: FindingStatus = FindingStatus.OPEN
    created_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "Finding":
        document = document.copy()
        document["finding_id"] = str(document.pop("_id"))
        document["run_id"] = str(document["run_id"])
        return cls.model_validate(document)
