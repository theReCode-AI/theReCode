from app.db.repositories.issue_group_repository import IssueGroupRepository
from app.models.issue_group import IssueGroup


class InMemoryIssueGroupRepository(IssueGroupRepository):
    def __init__(self) -> None:
        self._issue_groups: dict[str, list[IssueGroup]] = {}

    def replace_for_run(self, run_id: str, issue_groups: list[IssueGroup]) -> list[IssueGroup]:
        self._issue_groups[run_id] = list(issue_groups)
        return list(issue_groups)

    def list_by_run(self, run_id: str) -> list[IssueGroup]:
        return list(self._issue_groups.get(run_id, []))
