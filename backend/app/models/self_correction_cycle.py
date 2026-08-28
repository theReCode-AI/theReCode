from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.self_correction_enums import SelfCorrectionStatus


class SelfCorrectionCycle(BaseModel):
    """Persisted record of a self-correction retry after verification failure."""

    model_config = ConfigDict(populate_by_name=True)

    self_correction_cycle_id: str
    run_id: str
    patch_plan_id: str
    iteration_number: int = Field(ge=1)
    prior_fix_attempt_id: str
    prior_verification_result_id: str
    root_cause: str
    failure_summary: str
    rollback_applied: bool = False
    retry_fix_attempt_id: str | None = None
    retry_verification_result_id: str | None = None
    status: SelfCorrectionStatus
    error_message: str | None = None
    created_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "SelfCorrectionCycle":
        document = document.copy()
        document["self_correction_cycle_id"] = str(document.pop("_id"))
        document["run_id"] = str(document["run_id"])
        document["patch_plan_id"] = str(document["patch_plan_id"])
        document["prior_fix_attempt_id"] = str(document["prior_fix_attempt_id"])
        document["prior_verification_result_id"] = str(document["prior_verification_result_id"])
        if document.get("retry_fix_attempt_id") is not None:
            document["retry_fix_attempt_id"] = str(document["retry_fix_attempt_id"])
        if document.get("retry_verification_result_id") is not None:
            document["retry_verification_result_id"] = str(
                document["retry_verification_result_id"],
            )
        return cls.model_validate(document)
