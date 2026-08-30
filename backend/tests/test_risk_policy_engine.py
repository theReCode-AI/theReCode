from datetime import UTC, datetime

from bson import ObjectId

from app.adk.risk.policy_engine import RiskPolicyEngine
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
from app.models.risk_enums import AutonomyDecision


def _patch_plan(
    *,
    patch_plan_id: str | None = None,
    estimated_risk: RiskLevel = RiskLevel.LOW,
    scope: FixScope = FixScope.SINGLE_FILE,
    affected_files: list[str] | None = None,
    change_type: str = ChangeType.LINT_FIX.value,
) -> PatchPlan:
    now = datetime.now(UTC)
    files = affected_files or ["src/utils.py"]
    return PatchPlan(
        patch_plan_id=patch_plan_id or str(ObjectId()),
        run_id="run-1",
        issue_group_id=str(ObjectId()),
        title="Lint issue",
        root_cause="Unused import",
        affected_files=files,
        expected_modifications=[
            ExpectedModification(
                file=files[0],
                description="Remove unused import",
                change_type=change_type,
            ),
        ],
        expected_tests=["uv run ruff check src/utils.py"],
        estimated_risk=estimated_risk,
        expected_scope=scope,
        solution_rationale="Safe lint fix",
        rollback_strategy="Revert file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )


def test_policy_allows_autonomous_low_risk_lint_plan() -> None:
    decisions = RiskPolicyEngine().assess("run-1", [_patch_plan()])

    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.assessed_risk == RiskLevel.LOW
    assert decision.autonomy_decision == AutonomyDecision.AUTONOMOUS
    assert decision.approval_required is False
    assert decision.autonomous_fix_allowed is True


def test_policy_requires_approval_for_security_remediation() -> None:
    plan = _patch_plan(
        estimated_risk=RiskLevel.HIGH,
        change_type=ChangeType.SECURITY_REMEDIATION.value,
        affected_files=["src/api.py"],
    )

    decision = RiskPolicyEngine().assess("run-1", [plan])[0]

    assert decision.assessed_risk == RiskLevel.HIGH
    assert decision.autonomy_decision == AutonomyDecision.REQUIRES_APPROVAL
    assert decision.approval_required is True
    assert "security_remediation" in decision.policy_rules


def test_policy_blocks_sensitive_credential_files() -> None:
    plan = _patch_plan(
        estimated_risk=RiskLevel.CRITICAL,
        change_type=ChangeType.SECRET_REMOVAL.value,
        affected_files=["config/.env"],
    )

    decision = RiskPolicyEngine().assess("run-1", [plan])[0]

    assert decision.assessed_risk == RiskLevel.BLOCKED
    assert decision.autonomy_decision == AutonomyDecision.BLOCKED
    assert decision.approval_required is True
    assert decision.autonomous_fix_allowed is False
    assert "blocked_file_pattern" in decision.policy_rules


def test_policy_requires_approval_for_auth_file_changes() -> None:
    plan = _patch_plan(
        estimated_risk=RiskLevel.MEDIUM,
        change_type=ChangeType.SECURITY_REMEDIATION.value,
        affected_files=["src/auth/login.py"],
    )

    decision = RiskPolicyEngine().assess("run-1", [plan])[0]

    assert decision.assessed_risk == RiskLevel.HIGH
    assert decision.approval_required is True
    assert "authentication_change" in decision.policy_rules
