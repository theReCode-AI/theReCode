from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.regression_test_enums import RegressionTestStatus


class RegressionTestResult(BaseModel):
    """Persisted regression test outcome for a verified patch plan."""

    model_config = ConfigDict(populate_by_name=True)

    regression_test_id: str
    run_id: str
    patch_plan_id: str
    fix_attempt_id: str
    verification_result_id: str
    status: RegressionTestStatus
    eligible: bool
    test_file_path: str | None = None
    targeted_exit_code: int | None = None
    targeted_tests: int = Field(ge=0, default=0)
    targeted_passed: int = Field(ge=0, default=0)
    suite_exit_code: int | None = None
    suite_tests: int = Field(ge=0, default=0)
    suite_passed: int = Field(ge=0, default=0)
    failure_summary: str | None = None
    artifact_path: str | None = None
    created_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "RegressionTestResult":
        document = document.copy()
        document["regression_test_id"] = str(document.pop("_id"))
        document["run_id"] = str(document["run_id"])
        document["patch_plan_id"] = str(document["patch_plan_id"])
        document["fix_attempt_id"] = str(document["fix_attempt_id"])
        document["verification_result_id"] = str(document["verification_result_id"])
        return cls.model_validate(document)
