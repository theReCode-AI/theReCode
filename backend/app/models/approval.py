from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.approval_enums import ApprovalStatus, ApprovalTrigger, HumanDecision
from app.models.patch_plan_enums import RiskLevel


class HumanApproval(BaseModel):
    """Persisted human approval request and decision for a gated run."""

    model_config = ConfigDict(populate_by_name=True)

    approval_id: str
    run_id: str
    patch_plan_id: str | None = None
    trigger: ApprovalTrigger
    status: ApprovalStatus = ApprovalStatus.PENDING
    reason: str
    issue_title: str | None = None
    root_cause: str | None = None
    risk_level: RiskLevel | None = None
    affected_files: list[str] = Field(default_factory=list)
    diff_artifact_path: str | None = None
    evidence_summary: str | None = None
    expected_tests: list[str] = Field(default_factory=list)
    verification_summary: str | None = None
    reviewer_feedback: list[str] = Field(default_factory=list)
    confidence: str | None = None
    human_decision: HumanDecision | None = None
    human_feedback: str | None = None
    decided_by_user_id: str | None = None
    decided_at: datetime | None = None
    artifact_path: str | None = None
    created_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "HumanApproval":
        document = document.copy()
        document["approval_id"] = str(document.pop("_id"))
        document["run_id"] = str(document["run_id"])
        if document.get("patch_plan_id") is not None:
            document["patch_plan_id"] = str(document["patch_plan_id"])
        if document.get("decided_by_user_id") is not None:
            document["decided_by_user_id"] = str(document["decided_by_user_id"])
        return cls.model_validate(document)
