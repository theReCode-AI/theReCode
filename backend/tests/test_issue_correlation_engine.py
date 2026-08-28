from datetime import UTC, datetime

from bson import ObjectId

from app.adk.correlation.engine import FindingCorrelator
from app.models.finding import Finding
from app.models.finding_enums import (
    DiagnosticAgentName,
    FindingFixability,
    FindingSeverity,
    FindingStatus,
)


def _finding(
    *,
    file: str | None = "src/api.py",
    line_start: int | None = 42,
    category: str = "command_injection",
    agent: DiagnosticAgentName = DiagnosticAgentName.SECURITY,
    tool: str = "semgrep",
    rule_id: str | None = "python.lang.security.audit",
    message: str = "Possible command injection",
    severity: FindingSeverity = FindingSeverity.HIGH,
    confidence: float = 0.9,
) -> Finding:
    now = datetime.now(UTC)
    return Finding(
        finding_id=str(ObjectId()),
        run_id="run-1",
        agent=agent,
        tool=tool,
        category=category,
        severity=severity,
        confidence=confidence,
        file=file,
        line_start=line_start,
        line_end=line_start,
        message=message,
        rule_id=rule_id,
        evidence=message,
        fixability=FindingFixability.AGENT,
        status=FindingStatus.OPEN,
        created_at=now,
    )


def test_correlator_groups_cross_tool_security_findings() -> None:
    correlator = FindingCorrelator()
    findings = [
        _finding(tool="semgrep", agent=DiagnosticAgentName.SECURITY),
        _finding(
            tool="bandit",
            agent=DiagnosticAgentName.SECURITY,
            rule_id="B602",
            message="subprocess call with shell=True",
        ),
    ]

    issue_groups = correlator.correlate("run-1", findings)

    assert len(issue_groups) == 1
    assert len(issue_groups[0].finding_ids) == 2
    assert issue_groups[0].priority_rank == 1
    assert "Multiple security scanners" in issue_groups[0].root_cause


def test_correlator_merges_duplicate_findings() -> None:
    correlator = FindingCorrelator()
    findings = [
        _finding(tool="ruff", agent=DiagnosticAgentName.CODE_QUALITY, category="unused_variable"),
        _finding(
            tool="ruff",
            agent=DiagnosticAgentName.CODE_QUALITY,
            category="unused_variable",
            message="Possible command injection",
        ),
    ]
    findings[1] = findings[1].model_copy(
        update={
            "message": findings[0].message,
            "category": findings[0].category,
            "rule_id": findings[0].rule_id,
        },
    )

    issue_groups = correlator.correlate("run-1", findings)

    assert len(issue_groups) == 1
    assert len(issue_groups[0].finding_ids) == 1
    assert issue_groups[0].duplicate_count == 1
    assert "Duplicate reports" in issue_groups[0].root_cause


def test_correlator_prioritizes_critical_issues_first() -> None:
    correlator = FindingCorrelator()
    findings = [
        _finding(
            file="src/low.py",
            line_start=1,
            category="unused_variable",
            agent=DiagnosticAgentName.CODE_QUALITY,
            tool="ruff",
            severity=FindingSeverity.LOW,
            confidence=0.5,
            message="unused import",
            rule_id="F401",
        ),
        _finding(
            file="config.py",
            line_start=3,
            category="hardcoded_secret",
            agent=DiagnosticAgentName.SECRET_CHECK,
            tool="gitleaks",
            severity=FindingSeverity.CRITICAL,
            confidence=0.99,
            message="AWS key detected",
            rule_id="aws-access-key",
        ),
    ]

    issue_groups = correlator.correlate("run-1", findings)

    assert len(issue_groups) == 2
    assert issue_groups[0].severity == FindingSeverity.CRITICAL
    assert issue_groups[0].priority_rank == 1
    assert issue_groups[1].priority_rank == 2
