import json
from datetime import UTC, datetime
from pathlib import Path

from app.adk.agents.memory_agent import MemoryAgent
from app.adk.events import AgentEventEmitter, WorkflowEvent
from app.adk.memory import MemoryExtractionContext, MemoryRetriever, build_planning_snippets
from app.adk.workflows.stages import OrchestrationStage
from app.core.logging import get_logger
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.approval_repository import ApprovalRepository
from app.db.repositories.fix_attempt_repository import FixAttemptRepository
from app.db.repositories.fix_plan_repository import FixPlanRepository
from app.db.repositories.memory_repository import MemoryNotFoundError, MemoryRepository
from app.db.repositories.peer_review_result_repository import PeerReviewResultRepository
from app.db.repositories.regression_test_result_repository import RegressionTestResultRepository
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.db.repositories.self_correction_cycle_repository import SelfCorrectionCycleRepository
from app.db.repositories.verification_result_repository import VerificationResultRepository
from app.models.agent_event import AgentEventType
from app.models.issue_group import IssueGroup
from app.models.memory_entry import MemoryEntry
from app.models.memory_enums import MemoryType
from app.schemas.memory import (
    CaptureRunMemoryResponse,
    MemoryEntryResponse,
    PlanningMemoryResponse,
)
from app.services.project_service import ProjectService
from app.services.run_service import RunService

logger = get_logger(__name__)

PROJECT_MEMORIES_ARTIFACT_NAME = "project_memories.json"


class MemoryService:
    """Capture durable project memories and retrieve them for planning."""

    def __init__(
        self,
        run_repository: RunRepository,
        run_service: RunService,
        project_service: ProjectService,
        fix_plan_repository: FixPlanRepository,
        approval_repository: ApprovalRepository,
        fix_attempt_repository: FixAttemptRepository,
        verification_result_repository: VerificationResultRepository,
        regression_test_result_repository: RegressionTestResultRepository,
        peer_review_result_repository: PeerReviewResultRepository,
        self_correction_cycle_repository: SelfCorrectionCycleRepository,
        memory_repository: MemoryRepository,
        event_repository: AgentEventRepository,
        memory_agent: MemoryAgent | None = None,
        memory_retriever: MemoryRetriever | None = None,
    ) -> None:
        self._run_repository = run_repository
        self._run_service = run_service
        self._project_service = project_service
        self._fix_plan_repository = fix_plan_repository
        self._approval_repository = approval_repository
        self._fix_attempt_repository = fix_attempt_repository
        self._verification_result_repository = verification_result_repository
        self._regression_test_result_repository = regression_test_result_repository
        self._peer_review_result_repository = peer_review_result_repository
        self._self_correction_cycle_repository = self_correction_cycle_repository
        self._memory_repository = memory_repository
        self._event_repository = event_repository
        self._memory_agent = memory_agent or MemoryAgent()
        self._memory_retriever = memory_retriever or MemoryRetriever()

    def capture_run_memory(self, user_id: str, run_id: str) -> CaptureRunMemoryResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        self._project_service.get_project(user_id, run.project_id)
        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        context = MemoryExtractionContext(
            run=run,
            patch_plans=self._fix_plan_repository.list_by_run(run_id),
            approvals=self._approval_repository.list_by_run(run_id),
            fix_attempts=self._fix_attempt_repository.list_by_run(run_id),
            verification_results=self._verification_result_repository.list_by_run(run_id),
            regression_results=self._regression_test_result_repository.list_by_run(run_id),
            peer_reviews=self._peer_review_result_repository.list_by_run(run_id),
            self_correction_cycles=self._self_correction_cycle_repository.list_by_run(run_id),
        )

        self._emit_memory_capture_started(run_id)
        started_at = datetime.now(UTC)
        extracted = self._memory_agent.capture(context)
        source_keys = [entry.source_key for entry in extracted]
        self._memory_repository.delete_by_run_and_source_keys(run_id, source_keys)

        persisted: list[MemoryEntry] = []
        for entry in extracted:
            output_dir = workspace.baseline / "memory" / entry.memory_id
            persisted.append(self._persist_entry(entry, output_dir))

        self._write_project_memories_artifact(workspace.baseline, run.project_id)
        self._emit_memory_capture_completed(run_id, len(persisted))

        completed_at = datetime.now(UTC)
        response = CaptureRunMemoryResponse(
            run_id=run_id,
            project_id=run.project_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            memories=[
                MemoryEntryResponse.model_validate(entry.model_dump()) for entry in persisted
            ],
            memory_count=len(persisted),
            project_memory_count=sum(
                1 for entry in persisted if entry.memory_type == MemoryType.PROJECT
            ),
            decision_memory_count=sum(
                1 for entry in persisted if entry.memory_type == MemoryType.DECISION
            ),
            failure_memory_count=sum(
                1 for entry in persisted if entry.memory_type == MemoryType.FAILURE
            ),
            success_memory_count=sum(
                1 for entry in persisted if entry.memory_type == MemoryType.SUCCESS_STRATEGY
            ),
        )

        logger.info(
            "Run memory captured",
            extra={
                "run_id": run_id,
                "project_id": run.project_id,
                "user_id": user_id,
                "memory_count": response.memory_count,
                "stage": "memory",
            },
        )
        return response

    def list_project_memories(self, user_id: str, project_id: str) -> list[MemoryEntryResponse]:
        self._project_service.get_project(user_id, project_id)
        memories = self._memory_repository.list_by_project(project_id)
        return [MemoryEntryResponse.model_validate(memory.model_dump()) for memory in memories]

    def get_project_memory(
        self,
        user_id: str,
        project_id: str,
        memory_id: str,
    ) -> MemoryEntryResponse:
        self._project_service.get_project(user_id, project_id)
        memory = self._memory_repository.get_by_id_for_project(memory_id, project_id)
        if memory is None:
            raise MemoryNotFoundError(memory_id)
        return MemoryEntryResponse.model_validate(memory.model_dump())

    def retrieve_planning_memory(
        self,
        user_id: str,
        run_id: str,
        issue_groups: list[IssueGroup],
    ) -> PlanningMemoryResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        project_memories = self._memory_repository.list_by_project(run.project_id)
        relevant = self._memory_retriever.retrieve(project_memories, issue_groups)
        snippets = build_planning_snippets(relevant)
        return PlanningMemoryResponse(
            run_id=run_id,
            memory_count=len(relevant),
            snippets=snippets,
        )

    def planning_snippets_for_run(
        self,
        user_id: str,
        run_id: str,
        issue_groups: list[IssueGroup],
    ) -> list[str]:
        return self.retrieve_planning_memory(user_id, run_id, issue_groups).snippets

    def _persist_entry(self, entry: MemoryEntry, output_dir: Path) -> MemoryEntry:
        output_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = output_dir / "memory.json"
        persisted = entry.model_copy(update={"artifact_path": str(artifact_path)})
        artifact_path.write_text(
            json.dumps(persisted.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return self._memory_repository.add(persisted)

    def _write_project_memories_artifact(self, baseline_dir: Path, project_id: str) -> Path:
        baseline_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = baseline_dir / PROJECT_MEMORIES_ARTIFACT_NAME
        memories = self._memory_repository.list_by_project(project_id)
        payload = [memory.model_dump(mode="json") for memory in memories]
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return artifact_path

    def _emit_memory_capture_started(self, run_id: str) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.MEMORY_CAPTURE_STARTED,
                stage=OrchestrationStage.MEMORY,
                agent="memory_agent",
                payload={"run_id": run_id},
            ),
        )

    def _emit_memory_capture_completed(self, run_id: str, memory_count: int) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.MEMORY_CAPTURE_COMPLETED,
                stage=OrchestrationStage.MEMORY,
                agent="memory_agent",
                payload={"run_id": run_id, "memory_count": memory_count},
            ),
        )
