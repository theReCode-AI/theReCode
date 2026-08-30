from datetime import UTC, datetime
from pathlib import Path

from bson import ObjectId

from app.adk.regression.engine import RegressionTestEngine
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
from app.models.regression_test_enums import RegressionTestStatus
from tests.scanner_mocks import build_mock_command_runner


def _patch_plan(change_type: ChangeType) -> PatchPlan:
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
                change_type=change_type.value,
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


def test_engine_skips_lint_only_fix(tmp_path: Path) -> None:
    working = tmp_path / "working"
    working.mkdir()
    output_dir = tmp_path / "output"
    engine = RegressionTestEngine(build_mock_command_runner())

    result = engine.run(working, _patch_plan(ChangeType.LINT_FIX), output_dir)

    assert result.status == RegressionTestStatus.SKIPPED
    assert result.eligible is False
    assert result.test_file_path is None


def test_engine_generates_and_passes_regression_test(tmp_path: Path) -> None:
    working = tmp_path / "working"
    working.mkdir()
    auth_file = working / "src" / "auth.py"
    auth_file.parent.mkdir(parents=True)
    auth_file.write_text("TOKEN = 'safe'\n", encoding="utf-8")
    output_dir = tmp_path / "output"
    engine = RegressionTestEngine(build_mock_command_runner())

    result = engine.run(working, _patch_plan(ChangeType.SECURITY_REMEDIATION), output_dir)

    assert result.status == RegressionTestStatus.PASSED
    assert result.eligible is True
    assert result.test_file_path is not None
    assert (working / result.test_file_path).is_file()
    assert result.targeted_passed >= 1
    assert result.suite_passed >= 1
