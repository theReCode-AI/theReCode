from datetime import UTC, datetime

from bson import ObjectId

from app.adk.regression.generator import RegressionTestGenerator
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel


def _patch_plan(change_type: ChangeType) -> PatchPlan:
    now = datetime.now(UTC)
    patch_plan_id = str(ObjectId())
    return PatchPlan(
        patch_plan_id=patch_plan_id,
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


def test_generator_skips_lint_only_fixes() -> None:
    generator = RegressionTestGenerator()
    result = generator.generate(_patch_plan(ChangeType.LINT_FIX))

    assert result.eligible is False
    assert "lint-only" in (result.skip_reason or "").lower()


def test_generator_skips_format_only_fixes() -> None:
    generator = RegressionTestGenerator()
    result = generator.generate(_patch_plan(ChangeType.FORMAT_FIX))

    assert result.eligible is False


def test_generator_creates_regression_test_for_meaningful_fix() -> None:
    generator = RegressionTestGenerator()
    result = generator.generate(_patch_plan(ChangeType.SECURITY_REMEDIATION))

    assert result.eligible is True
    assert result.relative_path.startswith("tests/regression/test_regression_")
    assert "src/auth.py" in result.content
    assert "Unsafe eval usage" in result.content
