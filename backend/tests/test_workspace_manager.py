from pathlib import Path

import pytest

from app.workspace import (
    WorkspaceAlreadyExistsError,
    WorkspaceManager,
    WorkspaceNotFoundError,
    WorkspacePathViolationError,
)
from app.workspace.constants import RUN_DIRECTORIES


@pytest.fixture
def workspace_manager(tmp_path: Path) -> WorkspaceManager:
    return WorkspaceManager(tmp_path)


def test_create_run_workspace_creates_layout(workspace_manager: WorkspaceManager) -> None:
    run_id = "674f1f77bcf86cd799439011"
    workspace = workspace_manager.create_run_workspace(run_id)

    assert workspace.run_id == run_id
    assert workspace.root.exists()
    for directory_name in RUN_DIRECTORIES:
        assert (workspace.root / directory_name).is_dir()


def test_create_run_workspace_is_idempotent_guard(workspace_manager: WorkspaceManager) -> None:
    run_id = "674f1f77bcf86cd799439012"
    workspace_manager.create_run_workspace(run_id)

    with pytest.raises(WorkspaceAlreadyExistsError):
        workspace_manager.create_run_workspace(run_id)


def test_get_run_workspace_missing_raises(workspace_manager: WorkspaceManager) -> None:
    with pytest.raises(WorkspaceNotFoundError):
        workspace_manager.get_run_workspace("674f1f77bcf86cd799439013")


def test_invalid_run_id_rejected(workspace_manager: WorkspaceManager) -> None:
    with pytest.raises(WorkspacePathViolationError):
        workspace_manager.create_run_workspace("../etc/passwd")


def test_resolve_run_path_blocks_traversal(workspace_manager: WorkspaceManager) -> None:
    run_id = "674f1f77bcf86cd799439014"
    workspace_manager.create_run_workspace(run_id)

    safe_path = workspace_manager.resolve_run_path(run_id, "logs/agent.log")
    assert safe_path.is_relative_to(workspace_manager.get_run_workspace(run_id).root)

    with pytest.raises(WorkspacePathViolationError):
        workspace_manager.resolve_run_path(run_id, "../../outside.txt")
