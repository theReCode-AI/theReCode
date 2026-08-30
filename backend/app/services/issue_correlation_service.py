import json
from datetime import UTC, datetime
from pathlib import Path

from app.adk.agents.issue_correlation_agent import IssueCorrelationAgent
from app.adk.events import AgentEventEmitter, WorkflowEvent
from app.adk.workflows.stages import OrchestrationStage
from app.core.logging import get_logger
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.finding_repository import FindingRepository
from app.db.repositories.issue_group_repository import IssueGroupRepository
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.models.agent_event import AgentEventType
from app.models.issue_group import IssueGroup
from app.models.run import RunStatus
from app.schemas.issue_group import IssueCorrelationResponse, IssueGroupResponse
from app.services.run_service import RunService

logger = get_logger(__name__)

ISSUE_GROUPS_ARTIFACT_NAME = "issue_groups.json"


class IssueCorrelationService:
    """Correlate diagnostic findings into prioritized issue groups."""

    def __init__(
        self,
        run_repository: RunRepository,
        run_service: RunService,
        finding_repository: FindingRepository,
        issue_group_repository: IssueGroupRepository,
        event_repository: AgentEventRepository,
        correlation_agent: IssueCorrelationAgent | None = None,
    ) -> None:
        self._run_repository = run_repository
        self._run_service = run_service
        self._finding_repository = finding_repository
        self._issue_group_repository = issue_group_repository
        self._event_repository = event_repository
        self._correlation_agent = correlation_agent or IssueCorrelationAgent()

    def correlate_run(self, user_id: str, run_id: str) -> IssueCorrelationResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        started_at = datetime.now(UTC)
        findings = self._finding_repository.list_by_run(run_id)
        issue_groups = self._correlation_agent.run(run_id, findings)
        persisted_groups = self._issue_group_repository.replace_for_run(run_id, issue_groups)

        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        self._write_issue_groups_artifact(workspace.baseline, persisted_groups)
        self._run_repository.update_status(run_id, user_id, RunStatus.PLANNING)
        self._emit_issue_group_events(run_id, persisted_groups)

        completed_at = datetime.now(UTC)
        duplicate_count = sum(group.duplicate_count for group in persisted_groups)
        response = IssueCorrelationResponse(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            issue_groups=[
                IssueGroupResponse.model_validate(group.model_dump())
                for group in persisted_groups
            ],
            issue_group_count=len(persisted_groups),
            finding_count=len(findings),
            duplicate_count=duplicate_count,
        )

        logger.info(
            "Issue correlation completed",
            extra={
                "run_id": run_id,
                "user_id": user_id,
                "issue_group_count": len(persisted_groups),
                "finding_count": len(findings),
                "stage": "issue_correlation",
            },
        )
        return response

    def list_issue_groups(self, user_id: str, run_id: str) -> list[IssueGroupResponse]:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        issue_groups = self._issue_group_repository.list_by_run(run_id)
        return [
            IssueGroupResponse.model_validate(group.model_dump())
            for group in issue_groups
        ]

    def _emit_issue_group_events(self, run_id: str, issue_groups: list[IssueGroup]) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        for issue_group in issue_groups:
            emitter.yield_event(
                WorkflowEvent(
                    event_type=AgentEventType.ISSUE_GROUP_CREATED,
                    stage=OrchestrationStage.ISSUE_CORRELATION,
                    agent="issue_correlation_agent",
                    payload={
                        "issue_group_id": issue_group.issue_group_id,
                        "title": issue_group.title,
                        "priority_rank": issue_group.priority_rank,
                        "priority_score": issue_group.priority_score,
                        "finding_count": len(issue_group.finding_ids),
                    },
                ),
            )

    @staticmethod
    def _write_issue_groups_artifact(baseline_dir: Path, issue_groups: list[IssueGroup]) -> Path:
        baseline_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = baseline_dir / ISSUE_GROUPS_ARTIFACT_NAME
        payload = [group.model_dump(mode="json") for group in issue_groups]
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return artifact_path
