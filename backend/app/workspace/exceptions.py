class WorkspaceError(Exception):
    """Base workspace error."""


class WorkspaceAlreadyExistsError(WorkspaceError):
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"Workspace for run {run_id} already exists")


class WorkspaceNotFoundError(WorkspaceError):
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"Workspace for run {run_id} not found")


class WorkspacePathViolationError(WorkspaceError):
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Path escapes workspace boundary: {path}")
