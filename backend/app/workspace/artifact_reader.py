from pathlib import Path


class WorkspaceArtifactNotFoundError(Exception):
    def __init__(self, artifact_path: str) -> None:
        self.artifact_path = artifact_path
        super().__init__(f"Artifact not found: {artifact_path}")


class WorkspaceArtifactAccessError(Exception):
    def __init__(self, message: str = "Artifact path is outside the run workspace") -> None:
        self.message = message
        super().__init__(message)


def read_workspace_text_file(workspace_root: Path, artifact_path: str) -> str:
    """Read a text artifact ensuring it stays within the run workspace."""
    root = workspace_root.resolve()
    resolved = Path(artifact_path).resolve()

    if resolved != root and root not in resolved.parents:
        raise WorkspaceArtifactAccessError()

    if not resolved.is_file():
        raise WorkspaceArtifactNotFoundError(artifact_path)

    return resolved.read_text(encoding="utf-8")
