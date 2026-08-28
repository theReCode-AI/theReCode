from datetime import datetime

from pydantic import BaseModel, Field

from app.models.self_correction_cycle import SelfCorrectionCycle


class SelfCorrectionCycleResponse(SelfCorrectionCycle):
    """API response for a persisted self-correction cycle."""


class RunSelfCorrectionResponse(BaseModel):
    run_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    cycles: list[SelfCorrectionCycleResponse]
    cycle_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    exhausted_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    run_status: str
