from app.db.repositories.finding_repository import FindingRepository
from app.models.finding import Finding


class InMemoryFindingRepository(FindingRepository):
    def __init__(self) -> None:
        self._findings: dict[str, list[Finding]] = {}

    def replace_for_run(self, run_id: str, findings: list[Finding]) -> list[Finding]:
        self._findings[run_id] = list(findings)
        return list(findings)

    def list_by_run(self, run_id: str) -> list[Finding]:
        return list(self._findings.get(run_id, []))
