from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.patch_plan_enums import RiskLevel
from app.models.risk_enums import AutonomyDecision


class RiskDecision(BaseModel):
    """Authoritative risk assessment for a patch plan."""

    model_config = ConfigDict(populate_by_name=True)

    risk_decision_id: str
    run_id: str
    patch_plan_id: str
    estimated_risk: RiskLevel
    assessed_risk: RiskLevel
    autonomy_decision: AutonomyDecision
    approval_required: bool
    autonomous_fix_allowed: bool
    policy_rules: list[str] = Field(default_factory=list)
    rationale: str
    created_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "RiskDecision":
        document = document.copy()
        document["risk_decision_id"] = str(document.pop("_id"))
        document["run_id"] = str(document["run_id"])
        document["patch_plan_id"] = str(document["patch_plan_id"])
        return cls.model_validate(document)
