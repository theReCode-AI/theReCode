from datetime import datetime

from pydantic import BaseModel, Field

from app.models.approval import HumanApproval
from app.models.approval_enums import HumanDecision


class HumanApprovalResponse(HumanApproval):
    """API response for a human approval request."""


class PrepareApprovalsResponse(BaseModel):
    run_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    approvals: list[HumanApprovalResponse]
    approval_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    run_status: str


class SubmitApprovalDecisionRequest(BaseModel):
    decision: HumanDecision
    feedback: str | None = None


class SubmitApprovalDecisionResponse(BaseModel):
    approval: HumanApprovalResponse
    run_status: str
    replanning_required: bool = False


class ApprovalDiffResponse(BaseModel):
    approval_id: str
    run_id: str
    diff_path: str
    content: str
