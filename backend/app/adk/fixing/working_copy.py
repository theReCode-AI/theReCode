import shutil
from pathlib import Path

from app.workspace.models import RunWorkspace


class WorkingCopyError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class WorkingCopyManager:
    """Prepare an editable working copy from the cloned repository."""

    def prepare(self, workspace: RunWorkspace) -> Path:
        repository = workspace.repository
        working = workspace.working

        if _has_content(working):
            return working

        if not repository.exists() or not any(repository.iterdir()):
            raise WorkingCopyError("Repository must be cloned before applying fixes")

        shutil.copytree(repository, working, dirs_exist_ok=True)

        return working


def _has_content(directory: Path) -> bool:
    return directory.exists() and any(directory.iterdir())
