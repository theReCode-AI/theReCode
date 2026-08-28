from datetime import datetime

from pydantic import BaseModel, Field

from app.models.patch_plan import ExpectedModification, PatchPlan


class ExpectedModificationResponse(ExpectedModification):
    """API response for a planned modification."""


class PatchPlanResponse(PatchPlan):
    """API response for a persisted patch plan."""


class FixPlanningResponse(BaseModel):
    run_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    patch_plans: list[PatchPlanResponse]
    patch_plan_count: int = Field(ge=0)
