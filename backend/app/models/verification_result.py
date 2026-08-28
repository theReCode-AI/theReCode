from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.verification_enums import (
    VerificationCheckStatus,
    VerificationCheckType,
    VerificationStatus,
)


class VerificationCheck(BaseModel):
    """Single command or scanner check executed during verification."""

    check_type: VerificationCheckType
    name: str
    status: VerificationCheckStatus
    exit_code: int | None = None
    message: str | None = None
    duration_ms: int = Field(ge=0, default=0)


class VerificationResult(BaseModel):
    """Persisted verification outcome for an applied fix attempt."""

    model_config = ConfigDict(populate_by_name=True)

    verification_result_id: str
    run_id: str
    fix_attempt_id: str
    patch_plan_id: str
    status: VerificationStatus
    checks: list[VerificationCheck] = Field(default_factory=list)
    passed_checks: int = Field(ge=0, default=0)
    failed_checks: int = Field(ge=0, default=0)
    skipped_checks: int = Field(ge=0, default=0)
    failure_summary: str | None = None
    artifact_path: str | None = None
    created_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "VerificationResult":
        document = document.copy()
        document["verification_result_id"] = str(document.pop("_id"))
        document["run_id"] = str(document["run_id"])
        document["fix_attempt_id"] = str(document["fix_attempt_id"])
        document["patch_plan_id"] = str(document["patch_plan_id"])
        return cls.model_validate(document)
