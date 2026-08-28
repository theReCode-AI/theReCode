from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.patch_plan_enums import FixScope, PatchPlanStatus, RiskLevel


class ExpectedModification(BaseModel):
    """Planned code change for a single file."""

    file: str
    description: str
    change_type: str


class PatchPlan(BaseModel):
    """Structured remediation plan for a correlated issue group."""

    model_config = ConfigDict(populate_by_name=True)

    patch_plan_id: str
    run_id: str
    issue_group_id: str
    title: str
    root_cause: str
    affected_files: list[str]
    expected_modifications: list[ExpectedModification]
    expected_tests: list[str]
    estimated_risk: RiskLevel
    expected_scope: FixScope
    solution_rationale: str
    rollback_strategy: str
    priority_rank: int = Field(ge=1)
    status: PatchPlanStatus = PatchPlanStatus.READY
    created_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "PatchPlan":
        document = document.copy()
        document["patch_plan_id"] = str(document.pop("_id"))
        document["run_id"] = str(document["run_id"])
        document["issue_group_id"] = str(document["issue_group_id"])
        return cls.model_validate(document)
