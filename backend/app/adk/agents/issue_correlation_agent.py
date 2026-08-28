from app.adk.correlation.engine import FindingCorrelator
from app.models.finding import Finding
from app.models.issue_group import IssueGroup


class IssueCorrelationAgent:
    """ADK specialist agent that correlates diagnostic findings into issue groups."""

    def __init__(self, correlator: FindingCorrelator | None = None) -> None:
        self._correlator = correlator or FindingCorrelator()

    def run(self, run_id: str, findings: list[Finding]) -> list[IssueGroup]:
        return self._correlator.correlate(run_id, findings)
