from datetime import datetime

from pydantic import BaseModel, Field

from app.models.verification_result import VerificationCheck, VerificationResult


class VerificationCheckResponse(VerificationCheck):
    """API response for a single verification check."""


class VerificationResultResponse(VerificationResult):
    """API response for a persisted verification result."""


class RunVerificationResponse(BaseModel):
    run_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    verification_results: list[VerificationResultResponse]
    result_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    run_status: str
