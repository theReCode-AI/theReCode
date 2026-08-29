"""Build markdown run reports from persisted run artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.models.approval import HumanApproval
from app.models.finding import Finding
from app.models.finding_enums import FindingSeverity
from app.models.fix_attempt import FixAttempt
from app.models.git_operation import GitOperation
from app.models.issue_group import IssueGroup
from app.models.memory_entry import MemoryEntry
from app.models.patch_plan import PatchPlan
from app.models.peer_review_result import PeerReviewResult
from app.models.regression_test_result import RegressionTestResult
from app.models.risk_decision import RiskDecision
from app.models.run import Run
from app.models.scan import BaselineDiagnosticsSummary
from app.models.self_correction_cycle import SelfCorrectionCycle
from app.models.verification_result import VerificationResult
from app.schemas.project import ProjectResponse, RepositoryResponse


@dataclass(frozen=True)
class ReportGenerationContext:
    run: Run
    project: ProjectResponse
    repository: RepositoryResponse | None
    baseline_summary: BaselineDiagnosticsSummary | None
    findings: list[Finding]
    issue_groups: list[IssueGroup]
    patch_plans: list[PatchPlan]
    risk_decisions: list[RiskDecision]
    fix_attempts: list[FixAttempt]
    verification_results: list[VerificationResult]
    self_correction_cycles: list[SelfCorrectionCycle]
    regression_results: list[RegressionTestResult]
    peer_reviews: list[PeerReviewResult]
    approvals: list[HumanApproval]
    memories: list[MemoryEntry]
    git_operations: list[GitOperation]
    duration_ms: int
    final_health_score: float
    tool_versions: dict[str, str]


@dataclass(frozen=True)
class GeneratedReportContent:
    markdown: str
    plain_text_lines: list[str]
    final_health_score: float
    pull_request_url: str | None
    branch_name: str | None
    commit_sha: str | None
    duration_ms: int
    tool_versions: dict[str, str]


class MarkdownReportBuilder:
    """Render a structured markdown report for a completed autonomous run."""

    def build(self, context: ReportGenerationContext) -> GeneratedReportContent:
        sections = [
            _header_section(context),
            _repository_section(context),
            _project_intelligence_section(context),
            _baseline_health_section(context),
            _findings_section(context.findings),
            _issue_groups_section(context.issue_groups),
            _fix_plans_section(context.patch_plans),
            _code_changes_section(context.fix_attempts),
            _risk_section(context.risk_decisions),
            _verification_section(context.verification_results),
            _self_correction_section(context.self_correction_cycles),
            _regression_section(context.regression_results),
            _peer_review_section(context.peer_reviews),
            _human_decisions_section(context.approvals),
            _memory_section(context.memories),
            _git_results_section(context.git_operations),
            _remaining_risks_section(context),
            _final_health_section(context.final_health_score),
            _tool_versions_section(context.tool_versions),
            _execution_duration_section(context.duration_ms),
        ]
        markdown = "\n\n".join(section for section in sections if section)
        plain_text_lines = [line for line in markdown.splitlines() if line.strip()]
        latest_git = _latest_git_operation(context.git_operations)
        return GeneratedReportContent(
            markdown=markdown,
            plain_text_lines=plain_text_lines,
            final_health_score=context.final_health_score,
            pull_request_url=latest_git.pull_request_url if latest_git else None,
            branch_name=latest_git.branch_name if latest_git else None,
            commit_sha=latest_git.commit_sha if latest_git else None,
            duration_ms=context.duration_ms,
            tool_versions=context.tool_versions,
        )


def compute_final_health_score(
    findings: list[Finding],
    verification_results: list[VerificationResult],
    peer_reviews: list[PeerReviewResult],
) -> float:
    score = 100.0
    failed_verifications = sum(
        1 for result in verification_results if result.status.value == "failed"
    )
    score -= failed_verifications * 15
    high_findings = sum(
        1
        for finding in findings
        if finding.severity in {FindingSeverity.HIGH, FindingSeverity.CRITICAL}
    )
    score -= min(high_findings * 5, 40)
    rejected_reviews = sum(1 for review in peer_reviews if review.verdict.value == "rejected")
    score -= rejected_reviews * 20
    return max(0.0, min(100.0, score))


def extract_tool_versions(
    baseline_summary: BaselineDiagnosticsSummary | None,
) -> dict[str, str]:
    if baseline_summary is None:
        return {}
    versions: dict[str, str] = {}
    for scan in baseline_summary.scans:
        if scan.tool_version:
            versions[scan.tool.value] = scan.tool_version
    return versions


def compute_execution_duration_ms(
    run: Run,
    baseline_summary: BaselineDiagnosticsSummary | None,
) -> int:
    if baseline_summary is not None:
        return baseline_summary.duration_ms
    return int((run.updated_at - run.created_at).total_seconds() * 1000)


def _header_section(context: ReportGenerationContext) -> str:
    return (
        f"# CodeThera Run Report\n\n"
        f"- Run ID: `{context.run.id}`\n"
        f"- Project: {context.project.name}\n"
        f"- Status: {context.run.status.value}\n"
        f"- Generated: {_format_datetime(datetime.now(UTC))}"
    )


def _repository_section(context: ReportGenerationContext) -> str:
    if context.repository is None:
        return "## Repository\n\nNo linked repository."
    return (
        "## Repository\n\n"
        f"- Provider: {context.repository.provider}\n"
        f"- Full name: `{context.repository.full_name}`\n"
        f"- Default branch: `{context.repository.default_branch}`"
    )


def _project_intelligence_section(context: ReportGenerationContext) -> str:
    intelligence = context.run.project_intelligence
    if intelligence is None:
        return "## Project Intelligence\n\nProject intelligence was not captured."
    return (
        "## Project Intelligence\n\n"
        f"- Architecture: {intelligence.architecture.value}\n"
        f"- Package manager: {intelligence.package_manager.value}\n"
        f"- Frameworks: {', '.join(intelligence.frameworks) or 'none'}\n"
        f"- Entrypoints: {', '.join(intelligence.entrypoints) or 'none'}\n"
        f"- Source directories: {', '.join(intelligence.source_directories) or 'none'}\n"
        f"- Test directories: {', '.join(intelligence.test_directories) or 'none'}"
    )


def _baseline_health_section(context: ReportGenerationContext) -> str:
    summary = context.baseline_summary
    if summary is None:
        return "## Baseline Health\n\nBaseline diagnostics were not executed."
    lines = [
        f"- Duration: {summary.duration_ms} ms",
        f"- Scans executed: {len(summary.scans)}",
    ]
    for scan in summary.scans:
        lines.append(f"- {scan.tool.value}: {scan.status.value}")
    return "## Baseline Health\n\n" + "\n".join(lines)


def _findings_section(findings: list[Finding]) -> str:
    if not findings:
        return "## Findings\n\nNo findings were recorded."
    lines = [
        f"- [{finding.severity.value}] {_format_file_location(finding.file, finding.line_start)} "
        f"{finding.message} ({finding.tool})"
        for finding in findings[:25]
    ]
    return "## Findings\n\n" + "\n".join(lines)


def _issue_groups_section(issue_groups: list[IssueGroup]) -> str:
    if not issue_groups:
        return "## Root Causes\n\nNo correlated issue groups."
    lines = [f"- {group.title}: {group.root_cause}" for group in issue_groups[:20]]
    return "## Root Causes\n\n" + "\n".join(lines)


def _fix_plans_section(patch_plans: list[PatchPlan]) -> str:
    if not patch_plans:
        return "## Fix Plans\n\nNo patch plans were generated."
    lines = [
        f"- {plan.title} ({plan.estimated_risk.value}): {plan.solution_rationale}"
        for plan in patch_plans[:20]
    ]
    return "## Fix Plans\n\n" + "\n".join(lines)


def _code_changes_section(fix_attempts: list[FixAttempt]) -> str:
    if not fix_attempts:
        return "## Code Changes\n\nNo fix attempts were recorded."
    lines = []
    for attempt in fix_attempts[:20]:
        changed = ", ".join(_format_file_location(file) for file in attempt.changed_files) or "none"
        lines.append(f"- Attempt {attempt.attempt_number} ({attempt.status.value}): {changed}")
    return "## Code Changes\n\n" + "\n".join(lines)


def _risk_section(risk_decisions: list[RiskDecision]) -> str:
    if not risk_decisions:
        return "## Risk Assessment\n\nNo risk decisions were recorded."
    lines = [
        f"- {decision.patch_plan_id}: {decision.assessed_risk.value} / "
        f"{decision.autonomy_decision.value}"
        for decision in risk_decisions[:20]
    ]
    return "## Risk Assessment\n\n" + "\n".join(lines)


def _verification_section(verification_results: list[VerificationResult]) -> str:
    if not verification_results:
        return "## Verification\n\nNo verification results were recorded."
    lines = [
        f"- {result.patch_plan_id}: {result.status.value}"
        + (f" — {result.failure_summary}" if result.failure_summary else "")
        for result in verification_results[:20]
    ]
    return "## Verification\n\n" + "\n".join(lines)


def _self_correction_section(cycles: list[SelfCorrectionCycle]) -> str:
    if not cycles:
        return "## Self-Correction Attempts\n\nNo self-correction cycles were required."
    lines = [
        f"- {cycle.patch_plan_id}: {cycle.status.value} — {cycle.failure_summary}"
        for cycle in cycles[:20]
    ]
    return "## Self-Correction Attempts\n\n" + "\n".join(lines)


def _regression_section(results: list[RegressionTestResult]) -> str:
    if not results:
        return "## Regression Tests\n\nNo regression test results were recorded."
    lines = [
        f"- {result.patch_plan_id}: {result.status.value}"
        + (f" ({_format_file_location(result.test_file_path)})" if result.test_file_path else "")
        for result in results[:20]
    ]
    return "## Regression Tests\n\n" + "\n".join(lines)


def _peer_review_section(peer_reviews: list[PeerReviewResult]) -> str:
    if not peer_reviews:
        return "## Peer Review\n\nPeer review was not executed."
    lines = [
        f"- {review.patch_plan_id}: {review.verdict.value} — {review.synthesis_summary}"
        for review in peer_reviews[:20]
    ]
    return "## Peer Review\n\n" + "\n".join(lines)


def _human_decisions_section(approvals: list[HumanApproval]) -> str:
    if not approvals:
        return "## Human Decisions\n\nNo human approvals were required."
    lines = []
    for approval in approvals[:20]:
        decision = (
            approval.human_decision.value if approval.human_decision else approval.status.value
        )
        lines.append(f"- {approval.trigger.value}: {decision} — {approval.reason}")
        if approval.human_feedback:
            lines.append(f"  Feedback: {approval.human_feedback}")
    return "## Human Decisions\n\n" + "\n".join(lines)


def _memory_section(memories: list[MemoryEntry]) -> str:
    if not memories:
        return "## Project Memory\n\nNo durable memories were captured."
    lines = [f"- [{memory.memory_type.value}] {memory.title}" for memory in memories[:20]]
    return "## Project Memory\n\n" + "\n".join(lines)


def _git_results_section(git_operations: list[GitOperation]) -> str:
    latest = _latest_git_operation(git_operations)
    if latest is None:
        return "## Git Results\n\nGit finalization was not completed."
    lines = [
        f"- Branch: `{latest.branch_name}`",
        f"- Base branch: `{latest.base_branch}`",
        f"- Commit: `{latest.commit_sha}`",
        f"- Pull request: {latest.pull_request_url or 'n/a'}",
        f"- Status: {latest.status.value}",
    ]
    return "## Git Results\n\n" + "\n".join(lines)


def _remaining_risks_section(context: ReportGenerationContext) -> str:
    high_risk_plans = [
        plan for plan in context.patch_plans if plan.estimated_risk.value in {"high", "critical"}
    ]
    if not high_risk_plans:
        return "## Remaining Risks\n\nNo high-risk patch plans remain open."
    lines = [f"- {plan.title}: {plan.estimated_risk.value}" for plan in high_risk_plans[:10]]
    return "## Remaining Risks\n\n" + "\n".join(lines)


def _final_health_section(score: float) -> str:
    return f"## Final Health Score\n\n**{score:.1f} / 100**"


def _tool_versions_section(tool_versions: dict[str, str]) -> str:
    if not tool_versions:
        return "## Tool Versions\n\nTool versions were not captured."
    lines = [f"- {tool}: {version}" for tool, version in sorted(tool_versions.items())]
    return "## Tool Versions\n\n" + "\n".join(lines)


def _execution_duration_section(duration_ms: int) -> str:
    return f"## Execution Duration\n\n{duration_ms} ms"


def _latest_git_operation(git_operations: list[GitOperation]) -> GitOperation | None:
    if not git_operations:
        return None
    return git_operations[-1]


def _format_datetime(value: datetime) -> str:
    return value.isoformat()


def _format_file_location(file: str | None, line_start: int | None = None) -> str:
    if not file:
        return "unknown"

    file_name = Path(file.replace("\\", "/")).name
    if line_start is not None:
        return f"{file_name}:{line_start}"
    return file_name
