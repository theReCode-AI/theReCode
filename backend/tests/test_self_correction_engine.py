from datetime import UTC, datetime

from bson import ObjectId

from app.adk.self_correction.failure_analyzer import FailureAnalyzer
from app.models.verification_enums import (
    VerificationCheckStatus,
    VerificationCheckType,
    VerificationStatus,
)
from app.models.verification_result import VerificationCheck, VerificationResult


def test_failure_analyzer_summarizes_failed_checks() -> None:
    verification = VerificationResult(
        verification_result_id=str(ObjectId()),
        run_id="run-1",
        fix_attempt_id=str(ObjectId()),
        patch_plan_id=str(ObjectId()),
        status=VerificationStatus.FAILED,
        checks=[
            VerificationCheck(
                check_type=VerificationCheckType.COMMAND,
                name="uv run ruff check src/utils.py",
                status=VerificationCheckStatus.FAILED,
                exit_code=1,
                message="lint still failing",
            ),
        ],
        passed_checks=0,
        failed_checks=1,
        failure_summary="lint still failing",
        created_at=datetime.now(UTC),
    )

    root_cause = FailureAnalyzer().analyze(verification)

    assert "ruff check" in root_cause
    assert "lint still failing" in root_cause
