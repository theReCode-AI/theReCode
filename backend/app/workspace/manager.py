import re
from pathlib import Path

from app.core.logging import get_logger
from app.workspace.exceptions import (
    WorkspaceAlreadyExistsError,
    WorkspaceNotFoundError,
    WorkspacePathViolationError,
)
from app.workspace.models import RunWorkspace

logger = get_logger(__name__)

RUN_ID_PATTERN = re.compile(r"^[a-f0-9]{24}$")


class WorkspaceManager:
    """Manage structured on-disk workspaces for autonomous runs."""

    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root.resolve()
        self._runs_root = self._workspace_root / "runs"
        self._runs_root.mkdir(parents=True, exist_ok=True)

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    @property
    def runs_root(self) -> Path:
        return self._runs_root

    def validate_run_id(self, run_id: str) -> str:
        if not RUN_ID_PATTERN.match(run_id):
            raise WorkspacePathViolationError(run_id)
        return run_id

    def get_run_workspace(self, run_id: str) -> RunWorkspace:
        safe_run_id = self.validate_run_id(run_id)
        run_root = (self._runs_root / safe_run_id).resolve()
        self._ensure_within_runs_root(run_root)

        if not run_root.exists():
            raise WorkspaceNotFoundError(safe_run_id)

        return RunWorkspace(run_id=safe_run_id, root=run_root)

    def create_run_workspace(self, run_id: str) -> RunWorkspace:
        safe_run_id = self.validate_run_id(run_id)
        workspace = RunWorkspace(run_id=safe_run_id, root=(self._runs_root / safe_run_id).resolve())
        self._ensure_within_runs_root(workspace.root)

        if workspace.root.exists():
            raise WorkspaceAlreadyExistsError(safe_run_id)

        for directory in workspace.all_directories():
            directory.mkdir(parents=True, exist_ok=False)

        logger.info(
            "Run workspace created",
            extra={"run_id": safe_run_id, "stage": "workspace_create"},
        )
        return workspace

    def ensure_run_workspace(self, run_id: str) -> RunWorkspace:
        try:
            return self.get_run_workspace(run_id)
        except WorkspaceNotFoundError:
            return self.create_run_workspace(run_id)

    def run_workspace_exists(self, run_id: str) -> bool:
        safe_run_id = self.validate_run_id(run_id)
        return (self._runs_root / safe_run_id).exists()

    def resolve_run_path(self, run_id: str, relative_path: str) -> Path:
        workspace = self.get_run_workspace(run_id)
        return self.resolve_within_workspace(workspace.root, relative_path)

    def resolve_within_workspace(self, workspace_root: Path, relative_path: str) -> Path:
        candidate = (workspace_root / relative_path).resolve()
        self._ensure_within_workspace(workspace_root, candidate)
        return candidate

    def _ensure_within_runs_root(self, path: Path) -> None:
        runs_root = self._runs_root.resolve()
        if path != runs_root and runs_root not in path.parents:
            raise WorkspacePathViolationError(str(path))

    def _ensure_within_workspace(self, workspace_root: Path, path: Path) -> None:
        workspace_root = workspace_root.resolve()
        resolved = path.resolve()
        if resolved != workspace_root and workspace_root not in resolved.parents:
            raise WorkspacePathViolationError(str(path))
