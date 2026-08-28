from bson import ObjectId

from app.core.logging import get_logger
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.models.run import Run, RunStatus
from app.schemas.run import RunCreate, RunResponse, RunWorkspaceResponse
from app.services.project_service import ProjectService
from app.workspace import RunWorkspace, WorkspaceManager

logger = get_logger(__name__)


class RunService:
    """Create and manage autonomous runs with structured workspaces."""

    def __init__(
        self,
        run_repository: RunRepository,
        project_service: ProjectService,
        workspace_manager: WorkspaceManager,
    ) -> None:
        self._run_repository = run_repository
        self._project_service = project_service
        self._workspace_manager = workspace_manager

    def create_run(self, user_id: str, payload: RunCreate) -> RunResponse:
        self._project_service.get_project(user_id, payload.project_id)
        if payload.repository_id:
            self._project_service.get_repository(
                user_id,
                payload.project_id,
                payload.repository_id,
            )

        run_id = str(ObjectId())
        workspace = self._workspace_manager.create_run_workspace(run_id)
        run = self._run_repository.create(
            run_id=run_id,
            project_id=payload.project_id,
            user_id=user_id,
            repository_id=payload.repository_id,
            workspace_path=str(workspace.root),
            status=RunStatus.CREATED,
        )

        logger.info(
            "Run created",
            extra={
                "run_id": run.id,
                "project_id": payload.project_id,
                "user_id": user_id,
                "stage": "run_create",
            },
        )
        return self._to_run_response(run)

    def get_run(self, user_id: str, run_id: str) -> RunResponse:
        run = self._require_run(user_id, run_id)
        return self._to_run_response(run)

    def list_runs(self, user_id: str, project_id: str) -> list[RunResponse]:
        self._project_service.get_project(user_id, project_id)
        runs = self._run_repository.list_by_project(project_id, user_id)
        return [self._to_run_response(run) for run in runs]

    def get_run_workspace(self, user_id: str, run_id: str) -> RunWorkspaceResponse:
        run = self._require_run(user_id, run_id)
        workspace = self._workspace_manager.get_run_workspace(run.id)
        return RunWorkspaceResponse.from_workspace(workspace)

    def get_workspace_for_run(self, user_id: str, run_id: str) -> RunWorkspace:
        self._require_run(user_id, run_id)
        return self._workspace_manager.get_run_workspace(run_id)

    def update_status(self, user_id: str, run_id: str, status: RunStatus) -> RunResponse:
        run = self._run_repository.update_status(run_id, user_id, status)
        if run is None:
            raise RunNotFoundError(run_id)
        return self._to_run_response(run)

    def _require_run(self, user_id: str, run_id: str) -> Run:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)
        return run

    @staticmethod
    def _to_run_response(run: Run) -> RunResponse:
        return RunResponse(
            id=run.id,
            project_id=run.project_id,
            user_id=run.user_id,
            repository_id=run.repository_id,
            status=run.status,
            workspace_path=run.workspace_path,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )
