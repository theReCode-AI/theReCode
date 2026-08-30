from datetime import UTC, datetime

from app.google_adk.tools import pipeline_tools
from app.schemas.fix_attempt import CodeFixResponse, FixAttemptResponse
from app.schemas.patch_plan import FixPlanningResponse, PatchPlanResponse
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.patch_plan_enums import FixScope, PatchPlanStatus, RiskLevel


def test_create_fix_plans_returns_patch_plan_ids(monkeypatch) -> None:
    plan = PatchPlanResponse(
        patch_plan_id="plan-1",
        run_id="run-1",
        issue_group_id="group-1",
        title="Fix lint",
        root_cause="Lint issues",
        affected_files=["app/main.py"],
        expected_modifications=[],
        expected_tests=["pytest"],
        estimated_risk=RiskLevel.LOW,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Apply lint fixes",
        rollback_strategy="Revert commit",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=datetime.now(UTC),
    )
    response = FixPlanningResponse(
        run_id="run-1",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        duration_ms=1,
        patch_plans=[plan],
        patch_plan_count=1,
    )

    class FakePlanner:
        def plan_run(self, user_id: str, run_id: str) -> FixPlanningResponse:
            return response

    class FakeServices:
        fix_planner_service = FakePlanner()

    monkeypatch.setattr(pipeline_tools, "get_run_context", lambda: type("Ctx", (), {"user_id": "u", "run_id": "run-1"})())
    monkeypatch.setattr(pipeline_tools, "get_service_container", lambda: FakeServices())

    result = pipeline_tools.create_fix_plans()

    assert result["status"] == "ok"
    assert result["plan_ids"] == ["plan-1"]


def test_apply_autonomous_fixes_returns_fix_attempt_ids(monkeypatch) -> None:
    attempt = FixAttemptResponse(
        fix_attempt_id="attempt-1",
        run_id="run-1",
        patch_plan_id="plan-1",
        attempt_number=1,
        status=FixAttemptStatus.APPLIED,
        planned_files=["app/main.py"],
        created_at=datetime.now(UTC),
    )
    response = CodeFixResponse(
        run_id="run-1",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        duration_ms=1,
        fix_attempts=[attempt],
        attempt_count=1,
        applied_count=1,
        skipped_count=0,
        failed_count=0,
        rolled_back_count=0,
        run_status="FIXING",
    )

    class FakeFixer:
        def fix_run(self, user_id: str, run_id: str) -> CodeFixResponse:
            return response

    class FakeServices:
        code_fix_service = FakeFixer()

    monkeypatch.setattr(pipeline_tools, "get_run_context", lambda: type("Ctx", (), {"user_id": "u", "run_id": "run-1"})())
    monkeypatch.setattr(pipeline_tools, "get_service_container", lambda: FakeServices())

    result = pipeline_tools.apply_autonomous_fixes()

    assert result["attempt_ids"] == ["attempt-1"]
