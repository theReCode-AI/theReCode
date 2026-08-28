from app.db.repositories.git_operation_repository import GitOperationRepository
from app.models.git_operation import GitOperation


class InMemoryGitOperationRepository(GitOperationRepository):
    def __init__(self) -> None:
        self._operations: dict[str, GitOperation] = {}

    def add(self, operation: GitOperation) -> GitOperation:
        self._operations[operation.git_operation_id] = operation
        return operation

    def list_by_run(self, run_id: str) -> list[GitOperation]:
        return [
            operation
            for operation in self._operations.values()
            if operation.run_id == run_id
        ]

    def get_by_id_for_run(self, git_operation_id: str, run_id: str) -> GitOperation | None:
        operation = self._operations.get(git_operation_id)
        if operation is None or operation.run_id != run_id:
            return None
        return operation
