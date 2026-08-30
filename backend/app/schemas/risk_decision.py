from datetime import datetime

from pydantic import BaseModel, Field

from app.models.risk_decision import RiskDecision


class RiskDecisionResponse(RiskDecision):
    """API response for a persisted risk decision."""


class RiskAssessmentResponse(BaseModel):
    run_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    risk_decisions: list[RiskDecisionResponse]
    decision_count: int = Field(ge=0)
    approval_required_count: int = Field(ge=0)
    autonomous_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    run_status: str
