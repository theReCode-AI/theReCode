from datetime import UTC, datetime

from bson import ObjectId

from app.adk.reporting.markdown_builder import (
    MarkdownReportBuilder,
    ReportGenerationContext,
    _findings_section,
    compute_final_health_score,
)
from app.models.finding import Finding
from app.models.finding_enums import (
    DiagnosticAgentName,
    FindingFixability,
    FindingSeverity,
    FindingStatus,
)
from app.models.git_operation import GitOperation
from app.models.git_operation_enums import GitOperationStatus
from app.models.run import Run, RunStatus
from app.models.verification_enums import VerificationStatus
from app.models.verification_result import VerificationResult
from app.schemas.project import ProjectResponse


def _run() -> Run:
    now = datetime.now(UTC)
    return Run(
        id=str(ObjectId()),
        project_id=str(ObjectId()),
        user_id=str(ObjectId()),
        status=RunStatus.REPORTING,
        workspace_path="/tmp/workspace",
        created_at=now,
        updated_at=now,
    )


def test_compute_final_health_score_penalizes_failures() -> None:
    now = datetime.now(UTC)
    findings = [
        Finding(
            finding_id=str(ObjectId()),
            run_id="run-1",
            agent=DiagnosticAgentName.SECURITY,
            tool="semgrep",
            category="security",
            severity=FindingSeverity.HIGH,
            confidence=0.9,
            file="src/auth.py",
            line_start=1,
            line_end=1,
            message="issue",
            evidence="issue",
            fixability=FindingFixability.AGENT,
            status=FindingStatus.OPEN,
            created_at=now,
        ),
    ]
    verification_results = [
        VerificationResult(
            verification_result_id=str(ObjectId()),
            run_id="run-1",
            fix_attempt_id=str(ObjectId()),
            patch_plan_id=str(ObjectId()),
            status=VerificationStatus.FAILED,
            failure_summary="tests failed",
            created_at=now,
        ),
    ]

    score = compute_final_health_score(findings, verification_results, [])

    assert score < 100.0


def test_markdown_builder_includes_git_results() -> None:
    now = datetime.now(UTC)
    run = _run()
    git_operation = GitOperation(
        git_operation_id=str(ObjectId()),
        run_id=run.id,
        project_id=run.project_id,
        repository_id=str(ObjectId()),
        provider="github",
        status=GitOperationStatus.PR_CREATED,
        branch_name="agent/run-security",
        base_branch="main",
        commit_sha="abc123",
        pull_request_url="https://github.com/org/repo/pull/1",
        pull_request_number=1,
        title="CodeThera: Security issue",
        description="Body",
        changed_files=["src/auth.py"],
        created_at=now,
    )
    project = ProjectResponse(
        id=run.project_id,
        user_id=run.user_id,
        name="Demo",
        description=None,
        created_at=now,
        updated_at=now,
    )
    context = ReportGenerationContext(
        run=run,
        project=project,
        repository=None,
        baseline_summary=None,
        findings=[],
        issue_groups=[],
        patch_plans=[],
        risk_decisions=[],
        fix_attempts=[],
        verification_results=[],
        self_correction_cycles=[],
        regression_results=[],
        peer_reviews=[],
        approvals=[],
        memories=[],
        git_operations=[git_operation],
        duration_ms=1200,
        final_health_score=85.0,
        tool_versions={"ruff": "0.8.0"},
    )

    content = MarkdownReportBuilder().build(context)

    assert "https://github.com/org/repo/pull/1" in content.markdown
    assert "agent/run-security" in content.markdown
    assert content.final_health_score == 85.0


def test_findings_section_uses_file_name_only() -> None:
    now = datetime.now(UTC)
    findings = [
        Finding(
            finding_id=str(ObjectId()),
            run_id="run-1",
            agent=DiagnosticAgentName.SECURITY,
            tool="ruff",
            category="import",
            severity=FindingSeverity.LOW,
            confidence=0.9,
            file="/home/user/workspace/runs/abc/repository/kimi_test.py",
            line_start=1,
            line_end=1,
            message="Import",
            evidence="import",
            fixability=FindingFixability.AGENT,
            status=FindingStatus.OPEN,
            created_at=now,
        ),
    ]

    section = _findings_section(findings)

    assert "[low] kimi_test.py:1 Import" in section
    assert "/home/user/workspace" not in section
