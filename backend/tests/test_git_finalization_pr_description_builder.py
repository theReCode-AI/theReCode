from datetime import UTC, datetime

from bson import ObjectId

from app.adk.git_finalization.pr_description_builder import (
    PullRequestDescriptionContext,
    build_branch_name,
    build_pull_request_description,
    build_pull_request_title,
)
from app.models.fix_attempt import FixAttempt
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel


def _patch_plan(run_id: str) -> PatchPlan:
    now = datetime.now(UTC)
    return PatchPlan(
        patch_plan_id=str(ObjectId()),
        run_id=run_id,
        issue_group_id=str(ObjectId()),
        title="Remove unsafe eval",
        root_cause="Unsafe eval usage",
        affected_files=["src/auth.py"],
        expected_modifications=[
            ExpectedModification(
                file="src/auth.py",
                description="Replace eval",
                change_type=ChangeType.SECURITY_REMEDIATION.value,
            ),
        ],
        expected_tests=["uv run pytest tests/test_auth.py"],
        estimated_risk=RiskLevel.MEDIUM,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Use safe parser",
        rollback_strategy="Revert file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )


def test_build_branch_name_uses_fix_prefix_and_full_run_id() -> None:
    run_id = str(ObjectId())
    patch_plan = _patch_plan(run_id)

    branch_name = build_branch_name(run_id, [patch_plan])

    assert branch_name == f"fix/{run_id}"
    assert build_branch_name(run_id) == f"fix/{run_id}"


def test_build_pull_request_description_includes_sections() -> None:
    run_id = str(ObjectId())
    patch_plan = _patch_plan(run_id)
    now = datetime.now(UTC)
    context = PullRequestDescriptionContext(
        patch_plans=[patch_plan],
        fix_attempts=[
            FixAttempt(
                fix_attempt_id=str(ObjectId()),
                run_id=run_id,
                patch_plan_id=patch_plan.patch_plan_id,
                attempt_number=1,
                status=FixAttemptStatus.APPLIED,
                planned_files=["src/auth.py"],
                changed_files=["src/auth.py"],
                created_at=now,
            ),
        ],
        verification_results=[],
        peer_reviews=[],
        self_correction_cycles=[],
        changed_files=["src/auth.py"],
    )

    description = build_pull_request_description(context)
    title = build_pull_request_title([patch_plan], run_id)

    assert "Remove unsafe eval" in title
    assert "## Problem" in description
    assert "## Root Cause" in description
    assert "src/auth.py" in description
    assert "Use safe parser" in description
