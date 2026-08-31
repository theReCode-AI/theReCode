import json
from datetime import UTC, datetime
from pathlib import Path

from app.adk.agents.fix_planner_agent import FixPlannerAgent
from app.adk.events import AgentEventEmitter, WorkflowEvent
from app.adk.workflows.stages import OrchestrationStage
from app.core.logging import get_logger
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.finding_repository import FindingRepository
from app.db.repositories.approval_repository import ApprovalRepository
from app.db.repositories.fix_plan_repository import FixPlanNotFoundError, FixPlanRepository
from app.db.repositories.issue_group_repository import IssueGroupRepository
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.models.agent_event import AgentEventType
from app.models.approval import HumanApproval
from app.models.approval_enums import HumanDecision
from app.models.issue_group import IssueGroup
from app.models.issue_group_enums import IssueGroupStatus
from app.models.patch_plan import PatchPlan
from app.models.run import RunStatus
from app.schemas.patch_plan import FixPlanningResponse, PatchPlanResponse
from app.services.human_approval_service import load_human_feedback_entries
from app.services.issue_correlation_service import ISSUE_GROUPS_ARTIFACT_NAME
from app.services.memory_service import MemoryService
from app.services.run_service import RunService

logger = get_logger(__name__)

FIX_PLANS_ARTIFACT_NAME = "fix_plans.json"


class IssueGroupsRequiredError(Exception):
    def __init__(
        self,
        message: str = "Issue groups must be created before fix planning",
    ) -> None:
        self.message = message
        super().__init__(message)


class FixPlannerService:
    """Create patch plans from correlated issue groups."""

    def __init__(
        self,
        run_repository: RunRepository,
        run_service: RunService,
        finding_repository: FindingRepository,
        issue_group_repository: IssueGroupRepository,
        fix_plan_repository: FixPlanRepository,
        event_repository: AgentEventRepository,
        planner_agent: FixPlannerAgent | None = None,
        memory_service: MemoryService | None = None,
        approval_repository: ApprovalRepository | None = None,
    ) -> None:
        self._run_repository = run_repository
        self._run_service = run_service
        self._finding_repository = finding_repository
        self._issue_group_repository = issue_group_repository
        self._fix_plan_repository = fix_plan_repository
        self._event_repository = event_repository
        self._planner_agent = planner_agent or FixPlannerAgent()
        self._memory_service = memory_service
        self._approval_repository = approval_repository

    def plan_run(self, user_id: str, run_id: str) -> FixPlanningResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        issue_groups = self._issue_group_repository.list_by_run(run_id)
        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        correlation_artifact = workspace.baseline / ISSUE_GROUPS_ARTIFACT_NAME
        if not issue_groups and not correlation_artifact.is_file():
            raise IssueGroupsRequiredError()

        started_at = datetime.now(UTC)
        findings = self._finding_repository.list_by_run(run_id)
        human_feedback = _human_feedback_by_issue_group(workspace.baseline)
        if self._approval_repository is not None:
            human_feedback = _merge_human_feedback(
                human_feedback,
                self._approval_repository.list_by_run(run_id),
                self._fix_plan_repository,
                run_id,
            )
        memory_snippets: list[str] = []
        if self._memory_service is not None:
            memory_snippets = self._memory_service.planning_snippets_for_run(
                user_id,
                run_id,
                issue_groups,
            )
        patch_plans = self._planner_agent.run(
            run_id,
            issue_groups,
            findings,
            human_feedback,
            memory_snippets,
        )
        persisted_plans = self._fix_plan_repository.replace_for_run(run_id, patch_plans)
        self._mark_issue_groups_planned(run_id, issue_groups)

        self._write_fix_plans_artifact(workspace.baseline, persisted_plans)
        self._run_repository.update_status(run_id, user_id, RunStatus.PLANNING)
        self._emit_fix_plan_events(run_id, persisted_plans)

        completed_at = datetime.now(UTC)
        response = FixPlanningResponse(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            patch_plans=[
                PatchPlanResponse.model_validate(plan.model_dump()) for plan in persisted_plans
            ],
            patch_plan_count=len(persisted_plans),
        )

        logger.info(
            "Fix planning completed",
            extra={
                "run_id": run_id,
                "user_id": user_id,
                "patch_plan_count": len(persisted_plans),
                "stage": "fix_planning",
            },
        )
        return response

    def list_patch_plans(self, user_id: str, run_id: str) -> list[PatchPlanResponse]:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        patch_plans = self._fix_plan_repository.list_by_run(run_id)
        return [PatchPlanResponse.model_validate(plan.model_dump()) for plan in patch_plans]

    def get_patch_plan(self, user_id: str, run_id: str, patch_plan_id: str) -> PatchPlanResponse:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        patch_plan = self._fix_plan_repository.get_by_id_for_run(patch_plan_id, run_id)
        if patch_plan is None:
            raise FixPlanNotFoundError(patch_plan_id)

        return PatchPlanResponse.model_validate(patch_plan.model_dump())

    def _mark_issue_groups_planned(self, run_id: str, issue_groups: list[IssueGroup]) -> None:
        updated_groups = [
            group.model_copy(update={"status": IssueGroupStatus.PLANNED}) for group in issue_groups
        ]
        self._issue_group_repository.replace_for_run(run_id, updated_groups)

    def _emit_fix_plan_events(self, run_id: str, patch_plans: list[PatchPlan]) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        for patch_plan in patch_plans:
            emitter.yield_event(
                WorkflowEvent(
                    event_type=AgentEventType.FIX_PLAN_CREATED,
                    stage=OrchestrationStage.FIX_PLANNING,
                    agent="fix_planner_agent",
                    payload={
                        "patch_plan_id": patch_plan.patch_plan_id,
                        "issue_group_id": patch_plan.issue_group_id,
                        "title": patch_plan.title,
                        "estimated_risk": patch_plan.estimated_risk.value,
                        "priority_rank": patch_plan.priority_rank,
                    },
                ),
            )

    @staticmethod
    def _write_fix_plans_artifact(baseline_dir: Path, patch_plans: list[PatchPlan]) -> Path:
        baseline_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = baseline_dir / FIX_PLANS_ARTIFACT_NAME
        payload = [plan.model_dump(mode="json") for plan in patch_plans]
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return artifact_path


def _human_feedback_by_issue_group(baseline_dir: Path) -> dict[str, str]:
    feedback_by_group: dict[str, str] = {}
    for entry in load_human_feedback_entries(baseline_dir):
        issue_group_id = entry.get("issue_group_id")
        feedback = entry.get("feedback")
        if issue_group_id and feedback:
            feedback_by_group[issue_group_id] = feedback
    return feedback_by_group


def _merge_human_feedback(
    feedback_by_group: dict[str, str],
    approvals: list[HumanApproval],
    fix_plan_repository: FixPlanRepository,
    run_id: str,
) -> dict[str, str]:
    merged = dict(feedback_by_group)
    for approval in approvals:
        if approval.human_decision != HumanDecision.REQUEST_CHANGES:
            continue
        feedback = (approval.human_feedback or "").strip()
        if not feedback:
            continue
        issue_group_id = None
        if approval.patch_plan_id is not None:
            patch_plan = fix_plan_repository.get_by_id_for_run(approval.patch_plan_id, run_id)
            if patch_plan is not None:
                issue_group_id = patch_plan.issue_group_id
        if issue_group_id:
            merged[issue_group_id] = feedback
    return merged
