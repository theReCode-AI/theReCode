import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.logging import get_logger
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.intelligence import RepositoryEmptyError, RepositoryInspector, RepositoryNotReadyError
from app.models.project_intelligence import ProjectIntelligence
from app.models.run import RunStatus
from app.schemas.project_intelligence import ProjectIntelligenceArtifactResponse
from app.services.run_service import RunService

logger = get_logger(__name__)

INTELLIGENCE_ARTIFACT_NAME = "project_intelligence.json"


class ProjectIntelligenceService:
    """Analyze cloned repositories and persist structured project intelligence."""

    def __init__(
        self,
        run_repository: RunRepository,
        run_service: RunService,
        inspector: RepositoryInspector | None = None,
    ) -> None:
        self._run_repository = run_repository
        self._run_service = run_service
        self._inspector = inspector or RepositoryInspector()

    def analyze_run(self, user_id: str, run_id: str) -> ProjectIntelligenceArtifactResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        repository_path = workspace.repository

        self._run_repository.update_status(run_id, user_id, RunStatus.ANALYZING)

        try:
            intelligence = self._inspector.inspect(repository_path)
        except (RepositoryNotReadyError, RepositoryEmptyError):
            self._run_repository.update_status(run_id, user_id, run.status)
            raise

        artifact_path = self._write_artifact(workspace.artifacts, intelligence)
        updated_run = self._run_repository.update_project_intelligence(
            run_id,
            user_id,
            intelligence,
            RunStatus.ANALYZING,
        )
        if updated_run is None:
            raise RunNotFoundError(run_id)

        logger.info(
            "Project intelligence analysis completed",
            extra={
                "run_id": run_id,
                "user_id": user_id,
                "package_manager": intelligence.package_manager.value,
                "frameworks": intelligence.frameworks,
                "stage": "project_intelligence",
            },
        )

        return ProjectIntelligenceArtifactResponse(
            run_id=run_id,
            artifact_path=str(artifact_path),
            analyzed_at=updated_run.analyzed_at or datetime.now(UTC),
            intelligence=intelligence,
        )

    def get_intelligence(self, user_id: str, run_id: str) -> ProjectIntelligenceArtifactResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        if run.project_intelligence is None or run.analyzed_at is None:
            raise RepositoryNotReadyError("Project intelligence is not available for this run")

        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        artifact_path = workspace.artifacts / INTELLIGENCE_ARTIFACT_NAME

        return ProjectIntelligenceArtifactResponse(
            run_id=run_id,
            artifact_path=str(artifact_path),
            analyzed_at=run.analyzed_at,
            intelligence=run.project_intelligence,
        )

    @staticmethod
    def _write_artifact(artifacts_dir: Path, intelligence: ProjectIntelligence) -> Path:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifacts_dir / INTELLIGENCE_ARTIFACT_NAME
        artifact_path.write_text(
            json.dumps(intelligence.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return artifact_path
