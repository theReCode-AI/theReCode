import json
from datetime import UTC, datetime
from pathlib import Path

from bson import ObjectId

from app.adk.agents.git_finalization_agent import GitFinalizationAgent
from app.adk.events import AgentEventEmitter, WorkflowEvent
from app.adk.git_finalization.engine import GitFinalizationContext
from app.adk.workflows.stages import OrchestrationStage
from app.core.logging import get_logger
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.approval_repository import ApprovalRepository
from app.db.repositories.fix_attempt_repository import FixAttemptRepository
from app.db.repositories.fix_plan_repository import FixPlanRepository
from app.db.repositories.git_credential_repository import GitCredentialNotFoundError
from app.db.repositories.git_operation_repository import (
    GitOperationNotFoundError,
    GitOperationRepository,
)
from app.db.repositories.peer_review_result_repository import PeerReviewResultRepository
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.db.repositories.self_correction_cycle_repository import SelfCorrectionCycleRepository
from app.db.repositories.verification_result_repository import VerificationResultRepository
from app.git import GitProviderFactory
from app.models.agent_event import AgentEventType
from app.models.approval_enums import ApprovalStatus
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.git_operation import GitOperation
from app.models.git_operation_enums import GitOperationStatus
from app.models.peer_review_enums import PeerReviewVerdict
from app.models.run import RunStatus
from app.models.verification_enums import VerificationStatus
from app.schemas.git_finalization import GitOperationResponse, RunGitFinalizationResponse
from app.services.git_credential_service import GitCredentialService
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.workspace.exceptions import WorkspaceNotFoundError

logger = get_logger(__name__)

_GIT_FINALIZATION_ALLOWED_STATUSES = frozenset(
    {
        RunStatus.FINAL_REVIEW,
        RunStatus.REPORTING,
        RunStatus.COMPLETED,
        RunStatus.FAILED,
    },
)

_GIT_FORCE_FINALIZATION_ALLOWED_STATUSES = frozenset(
    {
        RunStatus.FIXING,
        RunStatus.VERIFYING,
        RunStatus.SELF_CORRECTING,
        RunStatus.PEER_REVIEW,
        RunStatus.FINAL_REVIEW,
        RunStatus.REPORTING,
        RunStatus.COMPLETED,
        RunStatus.FAILED,
    },
)

GIT_OPERATIONS_ARTIFACT_NAME = "git_operations.json"


class RunNotReadyForGitFinalizationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class GitFinalizationService:
    """Create an agent branch, commit fixes, push, and open a pull request."""

    def __init__(
        self,
        run_repository: RunRepository,
        run_service: RunService,
        project_service: ProjectService,
        git_credential_service: GitCredentialService,
        provider_factory: GitProviderFactory,
        fix_plan_repository: FixPlanRepository,
        fix_attempt_repository: FixAttemptRepository,
        verification_result_repository: VerificationResultRepository,
        peer_review_result_repository: PeerReviewResultRepository,
        self_correction_cycle_repository: SelfCorrectionCycleRepository,
        approval_repository: ApprovalRepository,
        git_operation_repository: GitOperationRepository,
        event_repository: AgentEventRepository,
        finalization_agent: GitFinalizationAgent | None = None,
    ) -> None:
        self._run_repository = run_repository
        self._run_service = run_service
        self._project_service = project_service
        self._git_credential_service = git_credential_service
        self._provider_factory = provider_factory
        self._fix_plan_repository = fix_plan_repository
        self._fix_attempt_repository = fix_attempt_repository
        self._verification_result_repository = verification_result_repository
        self._peer_review_result_repository = peer_review_result_repository
        self._self_correction_cycle_repository = self_correction_cycle_repository
        self._approval_repository = approval_repository
        self._git_operation_repository = git_operation_repository
        self._event_repository = event_repository
        self._finalization_agent = finalization_agent or GitFinalizationAgent()

    def finalize_run(
        self,
        user_id: str,
        run_id: str,
        base_branch: str | None = None,
        *,
        force: bool = False,
    ) -> RunGitFinalizationResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        self._validate_prerequisites(run_id, run.status, run.repository_id, force=force)
        repository = self._project_service.get_repository(
            user_id,
            run.project_id,
            run.repository_id,
        )
        patch_plans = self._fix_plan_repository.list_by_run(run_id)
        fix_attempts = self._fix_attempt_repository.list_by_run(run_id)
        changed_files = _collect_changed_files(fix_attempts)
        if not changed_files and not force:
            raise RunNotReadyForGitFinalizationError(
                "Applied fix attempts with changed files are required before git finalization",
            )

        try:
            workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        except WorkspaceNotFoundError as exc:
            raise RunNotReadyForGitFinalizationError(
                "Run workspace is missing. Clone the repository from the run Overview page, then retry push.",
            ) from exc

        try:
            access_token = self._git_credential_service.get_access_token(
                user_id,
                repository.provider,
            )
        except GitCredentialNotFoundError as exc:
            raise RunNotReadyForGitFinalizationError(
                f"No {repository.provider} access token saved. Add your personal access token under Settings, then retry push.",
            ) from exc
        provider = self._provider_factory.get_provider(repository.provider)
        validation = provider.validate_repository(repository.full_name, access_token)
        if not validation.valid:
            raise RunNotReadyForGitFinalizationError(
                validation.message or "Linked repository is not accessible",
            )

        self._run_repository.update_status(run_id, user_id, RunStatus.PUSHING)
        self._emit_git_finalization_started(run_id)

        started_at = datetime.now(UTC)
        context = GitFinalizationContext(
            run_id=run_id,
            workspace=workspace,
            repository_full_name=repository.full_name,
            default_branch=base_branch or validation.default_branch or repository.default_branch,
            patch_plans=patch_plans,
            fix_attempts=fix_attempts,
            verification_results=self._verification_result_repository.list_by_run(run_id),
            peer_reviews=self._peer_review_result_repository.list_by_run(run_id),
            self_correction_cycles=self._self_correction_cycle_repository.list_by_run(run_id),
            changed_files=changed_files,
            force=force,
        )
        result = self._finalization_agent.finalize(context, provider, access_token)
        committed_files = result.changed_files if result.changed_files is not None else changed_files
        operation = self._persist_operation(
            run,
            repository.id,
            repository.provider,
            committed_files,
            result,
            workspace.baseline,
        )
        self._write_git_operations_artifact(workspace.baseline, run_id)

        if result.status == GitOperationStatus.PR_CREATED:
            self._run_repository.update_status(run_id, user_id, RunStatus.REPORTING)
            self._emit_git_pr_created(run_id, operation)
            self._emit_git_finalization_completed(run_id, operation.git_operation_id)
            run_status = RunStatus.REPORTING.value
        else:
            self._run_repository.update_status(run_id, user_id, RunStatus.FAILED)
            self._emit_git_finalization_failed(run_id, operation.failure_summary)
            raise RunNotReadyForGitFinalizationError(
                result.failure_summary
                or f"Git finalization failed with status {result.status.value}",
            )

        completed_at = datetime.now(UTC)
        response = RunGitFinalizationResponse(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            operation=GitOperationResponse.model_validate(operation.model_dump()),
            run_status=run_status,
        )

        logger.info(
            "Git finalization completed",
            extra={
                "run_id": run_id,
                "user_id": user_id,
                "status": operation.status.value,
                "stage": "git_finalization",
            },
        )
        return response

    def list_git_operations(self, user_id: str, run_id: str) -> list[GitOperationResponse]:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)
        operations = self._git_operation_repository.list_by_run(run_id)
        return [
            GitOperationResponse.model_validate(operation.model_dump())
            for operation in operations
        ]

    def get_git_operation(
        self,
        user_id: str,
        run_id: str,
        git_operation_id: str,
    ) -> GitOperationResponse:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)
        operation = self._git_operation_repository.get_by_id_for_run(git_operation_id, run_id)
        if operation is None:
            raise GitOperationNotFoundError(git_operation_id)
        return GitOperationResponse.model_validate(operation.model_dump())

    def _validate_prerequisites(
        self,
        run_id: str,
        status: RunStatus,
        repository_id: str | None,
        *,
        force: bool = False,
    ) -> None:
        if force:
            if status not in _GIT_FORCE_FINALIZATION_ALLOWED_STATUSES:
                raise RunNotReadyForGitFinalizationError(
                    f"Cannot force push while run is {status.value}",
                )
        elif status not in _GIT_FINALIZATION_ALLOWED_STATUSES:
            raise RunNotReadyForGitFinalizationError(
                "Run must complete peer review before git finalization",
            )
        if repository_id is None:
            raise RunNotReadyForGitFinalizationError("Run has no linked repository")

        existing_operations = self._git_operation_repository.list_by_run(run_id)
        if any(
            operation.status == GitOperationStatus.PR_CREATED for operation in existing_operations
        ):
            raise RunNotReadyForGitFinalizationError(
                "A pull request has already been created for this run",
            )

        pending_approvals = self._approval_repository.list_pending_by_run(run_id)
        if pending_approvals:
            raise RunNotReadyForGitFinalizationError(
                "All human approvals must be resolved before git finalization",
            )

        decided_approvals = [
            approval
            for approval in self._approval_repository.list_by_run(run_id)
            if approval.status != ApprovalStatus.PENDING
        ]
        if decided_approvals and any(
            approval.status == ApprovalStatus.REJECTED for approval in decided_approvals
        ):
            raise RunNotReadyForGitFinalizationError(
                "Rejected approvals block git finalization",
            )

        if force:
            return

        peer_reviews = self._peer_review_result_repository.list_by_run(run_id)
        if peer_reviews and any(
            review.verdict != PeerReviewVerdict.APPROVED for review in peer_reviews
        ):
            raise RunNotReadyForGitFinalizationError(
                "Peer review must be approved before git finalization",
            )

        applied_plan_ids = {
            attempt.patch_plan_id
            for attempt in self._fix_attempt_repository.list_by_run(run_id)
            if attempt.status == FixAttemptStatus.APPLIED
        }
        if not applied_plan_ids:
            raise RunNotReadyForGitFinalizationError(
                "At least one applied fix attempt is required before git finalization",
            )

        verification_results = self._verification_result_repository.list_by_run(run_id)
        if verification_results:
            passed_plan_ids = {
                result.patch_plan_id
                for result in verification_results
                if result.status == VerificationStatus.PASSED
            }
            if applied_plan_ids.isdisjoint(passed_plan_ids):
                raise RunNotReadyForGitFinalizationError(
                    "Applied fixes must pass verification before git finalization",
                )

    def _persist_operation(
        self,
        run,
        repository_id: str,
        provider: str,
        changed_files: list[str],
        result,
        baseline_dir: Path,
    ) -> GitOperation:
        git_operation_id = str(ObjectId())
        output_dir = baseline_dir / "git" / git_operation_id
        output_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = output_dir / "operation.json"
        operation = GitOperation(
            git_operation_id=git_operation_id,
            run_id=run.id,
            project_id=run.project_id,
            repository_id=repository_id,
            provider=provider,
            status=result.status,
            branch_name=result.branch_name,
            base_branch=result.base_branch,
            commit_sha=result.commit_sha,
            push_commit_sha=result.push_commit_sha,
            pull_request_url=result.pull_request_url,
            pull_request_number=result.pull_request_number,
            title=result.title,
            description=result.description,
            changed_files=changed_files,
            failure_summary=result.failure_summary,
            artifact_path=str(artifact_path),
            created_at=datetime.now(UTC),
        )
        artifact_path.write_text(
            json.dumps(operation.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return self._git_operation_repository.add(operation)

    def _write_git_operations_artifact(self, baseline_dir: Path, run_id: str) -> Path:
        baseline_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = baseline_dir / GIT_OPERATIONS_ARTIFACT_NAME
        operations = self._git_operation_repository.list_by_run(run_id)
        payload = [operation.model_dump(mode="json") for operation in operations]
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return artifact_path

    def _emit_git_finalization_started(self, run_id: str) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.GIT_FINALIZATION_STARTED,
                stage=OrchestrationStage.GIT_FINALIZATION,
                agent="git_finalization_agent",
                payload={"run_id": run_id},
            ),
        )

    def _emit_git_pr_created(self, run_id: str, operation: GitOperation) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.GIT_PR_CREATED,
                stage=OrchestrationStage.GIT_FINALIZATION,
                agent="git_finalization_agent",
                payload={
                    "git_operation_id": operation.git_operation_id,
                    "pull_request_url": operation.pull_request_url,
                    "branch_name": operation.branch_name,
                },
            ),
        )

    def _emit_git_finalization_completed(self, run_id: str, git_operation_id: str) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.GIT_FINALIZATION_COMPLETED,
                stage=OrchestrationStage.GIT_FINALIZATION,
                agent="git_finalization_agent",
                payload={"git_operation_id": git_operation_id},
            ),
        )

    def _emit_git_finalization_failed(self, run_id: str, failure_summary: str | None) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.GIT_FINALIZATION_FAILED,
                stage=OrchestrationStage.GIT_FINALIZATION,
                agent="git_finalization_agent",
                status="failed",
                message=failure_summary,
                payload={"failure_summary": failure_summary},
            ),
        )


def _collect_changed_files(fix_attempts) -> list[str]:
    changed_files: list[str] = []
    seen: set[str] = set()
    for attempt in fix_attempts:
        if attempt.status != FixAttemptStatus.APPLIED:
            continue
        for file_path in attempt.changed_files:
            if file_path not in seen:
                seen.add(file_path)
                changed_files.append(file_path)
    return changed_files
