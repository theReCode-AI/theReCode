from datetime import UTC, datetime
from pathlib import Path

from bson import ObjectId

from app.adk.peer_review.engine import PeerReviewEngine
from app.models.fix_attempt import FixAttempt
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
from app.models.peer_review_enums import PeerReviewVerdict, ReviewerDecision
from app.models.project_intelligence import ProjectIntelligence
from app.models.regression_test_enums import RegressionTestStatus
from app.models.regression_test_result import RegressionTestResult
from app.models.verification_enums import VerificationStatus
from app.models.verification_result import VerificationResult


def _patch_plan() -> PatchPlan:
    now = datetime.now(UTC)
    return PatchPlan(
        patch_plan_id=str(ObjectId()),
        run_id=str(ObjectId()),
        issue_group_id=str(ObjectId()),
        title="Security issue",
        root_cause="Unsafe eval usage",
        affected_files=["src/auth.py"],
        expected_modifications=[
            ExpectedModification(
                file="src/auth.py",
                description="Remove eval",
                change_type=ChangeType.SECURITY_REMEDIATION.value,
            ),
        ],
        expected_tests=["uv run pytest tests/test_auth.py"],
        estimated_risk=RiskLevel.MEDIUM,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Replace eval with safe parser",
        rollback_strategy="Revert file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )


def _fix_attempt(run_id: str, patch_plan_id: str, diff_path: Path) -> FixAttempt:
    return FixAttempt(
        fix_attempt_id=str(ObjectId()),
        run_id=run_id,
        patch_plan_id=patch_plan_id,
        attempt_number=1,
        status=FixAttemptStatus.APPLIED,
        planned_files=["src/auth.py"],
        changed_files=["src/auth.py"],
        diff_artifact_path=str(diff_path),
        created_at=datetime.now(UTC),
    )


def _verification_result(
    run_id: str,
    patch_plan_id: str,
    fix_attempt_id: str,
) -> VerificationResult:
    return VerificationResult(
        verification_result_id=str(ObjectId()),
        run_id=run_id,
        fix_attempt_id=fix_attempt_id,
        patch_plan_id=patch_plan_id,
        status=VerificationStatus.PASSED,
        created_at=datetime.now(UTC),
    )


def _regression_result(
    run_id: str,
    patch_plan_id: str,
    fix_attempt_id: str,
    verification_result_id: str,
) -> RegressionTestResult:
    return RegressionTestResult(
        regression_test_id=str(ObjectId()),
        run_id=run_id,
        patch_plan_id=patch_plan_id,
        fix_attempt_id=fix_attempt_id,
        verification_result_id=verification_result_id,
        status=RegressionTestStatus.PASSED,
        eligible=True,
        test_file_path="tests/regression/test_regression_example.py",
        targeted_passed=1,
        suite_passed=1,
        created_at=datetime.now(UTC),
    )


def test_engine_approves_clean_security_fix(tmp_path: Path) -> None:
    working = tmp_path / "working"
    working.mkdir()
    diff_path = tmp_path / "changes.diff"
    diff_path.write_text(
        "--- a/src/auth.py\n+++ b/src/auth.py\n@@\n-TOKEN = eval('1')\n+TOKEN = 'safe'\n",
        encoding="utf-8",
    )

    patch_plan = _patch_plan()
    fix_attempt = _fix_attempt(patch_plan.run_id, patch_plan.patch_plan_id, diff_path)
    verification = _verification_result(
        patch_plan.run_id,
        patch_plan.patch_plan_id,
        fix_attempt.fix_attempt_id,
    )
    regression = _regression_result(
        patch_plan.run_id,
        patch_plan.patch_plan_id,
        fix_attempt.fix_attempt_id,
        verification.verification_result_id,
    )

    result = PeerReviewEngine().review(
        working,
        patch_plan,
        fix_attempt,
        verification,
        regression,
        ProjectIntelligence(source_directories=["src"]),
    )

    assert result.verdict == PeerReviewVerdict.APPROVED
    assert len(result.reviewer_opinions) == 3
    assert all(
        opinion.decision == ReviewerDecision.APPROVE for opinion in result.reviewer_opinions
    )


def test_engine_rejects_scope_violation(tmp_path: Path) -> None:
    working = tmp_path / "working"
    working.mkdir()
    diff_path = tmp_path / "changes.diff"
    diff_path.write_text("", encoding="utf-8")

    patch_plan = _patch_plan()
    fix_attempt = FixAttempt(
        fix_attempt_id=str(ObjectId()),
        run_id=patch_plan.run_id,
        patch_plan_id=patch_plan.patch_plan_id,
        attempt_number=1,
        status=FixAttemptStatus.APPLIED,
        planned_files=["src/auth.py"],
        changed_files=["src/auth.py", "config/secrets.py"],
        scope_violation=True,
        unexpected_files=["config/secrets.py"],
        diff_artifact_path=str(diff_path),
        created_at=datetime.now(UTC),
    )
    verification = _verification_result(
        patch_plan.run_id,
        patch_plan.patch_plan_id,
        fix_attempt.fix_attempt_id,
    )
    regression = _regression_result(
        patch_plan.run_id,
        patch_plan.patch_plan_id,
        fix_attempt.fix_attempt_id,
        verification.verification_result_id,
    )

    result = PeerReviewEngine().review(
        working,
        patch_plan,
        fix_attempt,
        verification,
        regression,
        None,
    )

    assert result.verdict == PeerReviewVerdict.REJECTED
    assert result.blocking_issues
