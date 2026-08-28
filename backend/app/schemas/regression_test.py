from datetime import datetime

from pydantic import BaseModel, Field

from app.models.regression_test_result import RegressionTestResult


class RegressionTestResultResponse(RegressionTestResult):
    """API response for a persisted regression test result."""


class RunRegressionTestResponse(BaseModel):
    run_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    regression_tests: list[RegressionTestResultResponse]
    result_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    run_status: str
