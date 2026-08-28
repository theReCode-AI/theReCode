from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.peer_review_enums import PeerReviewVerdict, ReviewerDecision, ReviewerRole


class ReviewerOpinion(BaseModel):
    """Independent opinion from a specialist peer reviewer."""

    reviewer: ReviewerRole
    decision: ReviewerDecision
    summary: str
    findings: list[str] = Field(default_factory=list)


class PeerReviewResult(BaseModel):
    """Persisted multi-agent peer review outcome for a patch plan."""

    model_config = ConfigDict(populate_by_name=True)

    peer_review_id: str
    run_id: str
    patch_plan_id: str
    fix_attempt_id: str
    verification_result_id: str
    regression_test_id: str
    verdict: PeerReviewVerdict
    reviewer_opinions: list[ReviewerOpinion] = Field(default_factory=list)
    synthesis_summary: str
    blocking_issues: list[str] = Field(default_factory=list)
    diff_artifact_path: str | None = None
    artifact_path: str | None = None
    created_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "PeerReviewResult":
        document = document.copy()
        document["peer_review_id"] = str(document.pop("_id"))
        document["run_id"] = str(document["run_id"])
        document["patch_plan_id"] = str(document["patch_plan_id"])
        document["fix_attempt_id"] = str(document["fix_attempt_id"])
        document["verification_result_id"] = str(document["verification_result_id"])
        document["regression_test_id"] = str(document["regression_test_id"])
        return cls.model_validate(document)
