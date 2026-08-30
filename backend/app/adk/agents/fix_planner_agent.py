from app.adk.planning.planner import FixPlannerEngine
from app.models.finding import Finding
from app.models.issue_group import IssueGroup
from app.models.patch_plan import PatchPlan


class FixPlannerAgent:
    """ADK specialist agent that converts issue groups into patch plans."""

    def __init__(self, planner: FixPlannerEngine | None = None) -> None:
        self._planner = planner or FixPlannerEngine()

    def run(
        self,
        run_id: str,
        issue_groups: list[IssueGroup],
        findings: list[Finding],
        human_feedback_by_issue_group: dict[str, str] | None = None,
        memory_snippets: list[str] | None = None,
    ) -> list[PatchPlan]:
        findings_by_id = {finding.finding_id: finding for finding in findings}
        return self._planner.plan(
            run_id,
            issue_groups,
            findings_by_id,
            human_feedback_by_issue_group,
            memory_snippets,
        )
