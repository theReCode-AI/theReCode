import pytest

from app.workspace.artifact_reader import (
    WorkspaceArtifactAccessError,
    WorkspaceArtifactNotFoundError,
    read_workspace_text_file,
)


def test_read_workspace_text_file_returns_content(tmp_path) -> None:
    artifact = tmp_path / "patches" / "plan" / "changes.diff"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("diff content", encoding="utf-8")

    content = read_workspace_text_file(tmp_path, str(artifact))
    assert content == "diff content"


def test_read_workspace_text_file_rejects_path_outside_workspace(tmp_path) -> None:
    outside = tmp_path.parent / "outside.diff"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(WorkspaceArtifactAccessError):
        read_workspace_text_file(tmp_path, str(outside))


def test_read_workspace_text_file_raises_when_missing(tmp_path) -> None:
    with pytest.raises(WorkspaceArtifactNotFoundError):
        read_workspace_text_file(tmp_path, str(tmp_path / "missing.diff"))
