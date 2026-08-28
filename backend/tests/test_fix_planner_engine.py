from datetime import UTC, datetime

from bson import ObjectId

from app.adk.planning.planner import FixPlannerEngine
from app.models.finding import Finding
from app.models.finding_enums import (
    DiagnosticAgentName,
    FindingFixability,
    FindingSeverity,
    FindingStatus,
)
from app.models.issue_group import IssueGroup
from app.models.issue_group_enums import IssueGroupStatus
from app.models.patch_plan_enums import ChangeType, FixScope, RiskLevel


def _finding(
    *,
    finding_id: str | None = None,
    file: str = "src/api.py",
    line_start: int = 42,
    category: str = "command_injection",
    agent: DiagnosticAgentName = DiagnosticAgentName.SECURITY,
    tool: str = "semgrep",
    severity: FindingSeverity = FindingSeverity.HIGH,
    message: str = "Possible command injection",
) -> Finding:
    now = datetime.now(UTC)
    return Finding(
        finding_id=finding_id or str(ObjectId()),
        run_id="run-1",
        agent=agent,
        tool=tool,
        category=category,
        severity=severity,
        confidence=0.9,
        file=file,
        line_start=line_start,
        line_end=line_start,
        message=message,
        rule_id="rule-1",
        evidence=message,
        fixability=FindingFixability.AGENT,
        status=FindingStatus.OPEN,
        created_at=now,
    )


def _issue_group(
    *,
    issue_group_id: str | None = None,
    finding_ids: list[str],
    categories: list[str],
    affected_files: list[str],
    priority_rank: int = 1,
    root_cause: str = "Security issue detected",
) -> IssueGroup:
    now = datetime.now(UTC)
    return IssueGroup(
        issue_group_id=issue_group_id or str(ObjectId()),
        run_id="run-1",
        title="Command Injection in src/api.py:42",
        summary="1 related finding",
        root_cause=root_cause,
        finding_ids=finding_ids,
        categories=categories,
        agents=[DiagnosticAgentName.SECURITY],
        tools=["semgrep"],
        severity=FindingSeverity.HIGH,
        priority_score=85.0,
        priority_rank=priority_rank,
        affected_files=affected_files,
        status=IssueGroupStatus.OPEN,
        created_at=now,
    )


def test_planner_builds_security_patch_plan() -> None:
    finding = _finding()
    issue_group = _issue_group(
        finding_ids=[finding.finding_id],
        categories=["command_injection"],
        affected_files=["src/api.py"],
    )

    plans = FixPlannerEngine().plan(
        "run-1",
        [issue_group],
        {finding.finding_id: finding},
    )

    assert len(plans) == 1
    plan = plans[0]
    assert plan.estimated_risk == RiskLevel.HIGH
    assert plan.expected_scope == FixScope.SINGLE_FILE
    assert plan.affected_files == ["src/api.py"]
    assert plan.expected_modifications[0].change_type == ChangeType.SECURITY_REMEDIATION.value
    assert any("semgrep" in test or "pytest" in test for test in plan.expected_tests)
    assert "baseline snapshot" in plan.rollback_strategy


def test_planner_builds_low_risk_lint_plan() -> None:
    finding = _finding(
        file="src/utils.py",
        line_start=5,
        category="unused_variable",
        agent=DiagnosticAgentName.CODE_QUALITY,
        tool="ruff",
        severity=FindingSeverity.LOW,
        message="unused variable",
    )
    issue_group = _issue_group(
        finding_ids=[finding.finding_id],
        categories=["unused_variable"],
        affected_files=["src/utils.py"],
        root_cause="Unused variable in src/utils.py",
    )

    plans = FixPlannerEngine().plan(
        "run-1",
        [issue_group],
        {finding.finding_id: finding},
    )

    plan = plans[0]
    assert plan.estimated_risk == RiskLevel.LOW
    assert plan.expected_modifications[0].change_type == ChangeType.LINT_FIX.value
    assert "ruff" in plan.expected_tests[0]


def test_planner_marks_secret_issues_as_critical() -> None:
    finding = _finding(
        file="config/settings.py",
        category="hardcoded_secret",
        agent=DiagnosticAgentName.SECRET_CHECK,
        tool="gitleaks",
        severity=FindingSeverity.CRITICAL,
        message="AWS key detected",
    )
    issue_group = _issue_group(
        finding_ids=[finding.finding_id],
        categories=["hardcoded_secret"],
        affected_files=["config/settings.py"],
        root_cause="Hardcoded secret detected",
    )

    plans = FixPlannerEngine().plan(
        "run-1",
        [issue_group],
        {finding.finding_id: finding},
    )

    plan = plans[0]
    assert plan.estimated_risk == RiskLevel.CRITICAL
    assert plan.expected_modifications[0].change_type == ChangeType.SECRET_REMOVAL.value
    assert "gitleaks" in " ".join(plan.expected_tests)


def test_fix_planner_includes_human_feedback() -> None:
    issue_group = _issue_group(
        finding_ids=["finding-1"],
        categories=["unused_variable"],
        affected_files=["src/utils.py"],
        root_cause="Unused variable",
    )
    finding = _finding(
        finding_id="finding-1",
        category="unused_variable",
        file="src/utils.py",
        tool="ruff",
    )

    plans = FixPlannerEngine().plan(
        "run-1",
        [issue_group],
        {finding.finding_id: finding},
        human_feedback_by_issue_group={
            issue_group.issue_group_id: "Preserve the public API surface",
        },
    )

    assert "Preserve the public API surface" in plans[0].solution_rationale


def test_fix_planner_includes_memory_snippets() -> None:
    issue_group = _issue_group(
        finding_ids=["finding-1"],
        categories=["unused_variable"],
        affected_files=["src/utils.py"],
        root_cause="Unused variable",
    )
    finding = _finding(
        finding_id="finding-1",
        category="unused_variable",
        file="src/utils.py",
        tool="ruff",
    )

    plans = FixPlannerEngine().plan(
        "run-1",
        [issue_group],
        {finding.finding_id: finding},
        memory_snippets=["Prior success: prefer minimal diffs"],
    )

    assert "Project memory: Prior success: prefer minimal diffs" in plans[0].solution_rationale
