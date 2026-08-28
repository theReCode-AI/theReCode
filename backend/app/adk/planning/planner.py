"""Deterministic fix planning engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from bson import ObjectId

from app.models.finding import Finding
from app.models.finding_enums import FindingSeverity
from app.models.issue_group import IssueGroup
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel

LINT_CATEGORIES = frozenset(
    {
        "unused_variable",
        "unused_import",
        "import_sort",
        "formatting",
        "lint",
    },
)
SECURITY_CATEGORIES = frozenset(
    {
        "command_injection",
        "sql_injection",
        "security",
        "insecure_deserialization",
        "path_traversal",
        "xss",
        "authentication",
        "authorization",
    },
)
SECRET_CATEGORIES = frozenset({"hardcoded_secret", "secret"})
DEPENDENCY_CATEGORIES = frozenset({"dependency_vulnerability", "vulnerable_dependency"})
HIGH_RISK_FILE_MARKERS = (
    "auth",
    "credential",
    "password",
    "secret",
    "token",
    "migration",
    "config",
    "security",
)


@dataclass(frozen=True)
class CategoryStrategy:
    change_type: ChangeType
    base_risk: RiskLevel
    scope: FixScope
    modification_template: str
    rationale_template: str
    tests: tuple[str, ...]


DEFAULT_STRATEGY = CategoryStrategy(
    change_type=ChangeType.MANUAL_REVIEW,
    base_risk=RiskLevel.MEDIUM,
    scope=FixScope.SINGLE_FILE,
    modification_template="Review and remediate {category} issue in {file}",
    rationale_template=(
        "Manual review is required because the issue category does not have "
        "a fully automated remediation path."
    ),
    tests=("uv run pytest",),
)

CATEGORY_STRATEGIES: dict[str, CategoryStrategy] = {
    "unused_variable": CategoryStrategy(
        change_type=ChangeType.LINT_FIX,
        base_risk=RiskLevel.LOW,
        scope=FixScope.SINGLE_FILE,
        modification_template="Remove or use the unused variable reported by {tool} in {file}",
        rationale_template=(
            "Ruff can safely remove or rewrite unused variables without changing behavior."
        ),
        tests=("uv run ruff check {file}", "uv run pytest"),
    ),
    "unused_import": CategoryStrategy(
        change_type=ChangeType.LINT_FIX,
        base_risk=RiskLevel.LOW,
        scope=FixScope.SINGLE_FILE,
        modification_template="Remove unused imports reported by {tool} in {file}",
        rationale_template="Unused imports are safe to remove and improve maintainability.",
        tests=("uv run ruff check {file}",),
    ),
    "formatting": CategoryStrategy(
        change_type=ChangeType.FORMAT_FIX,
        base_risk=RiskLevel.LOW,
        scope=FixScope.SINGLE_FILE,
        modification_template="Apply formatting corrections in {file}",
        rationale_template="Formatting-only changes are low risk and preserve behavior.",
        tests=("uv run ruff format --check {file}", "uv run ruff check {file}"),
    ),
    "test_failure": CategoryStrategy(
        change_type=ChangeType.TEST_FIX,
        base_risk=RiskLevel.MEDIUM,
        scope=FixScope.REPOSITORY,
        modification_template="Fix failing test behavior or update incorrect assertions",
        rationale_template=(
            "Test failures indicate broken behavior or outdated expectations that "
            "must be corrected before release."
        ),
        tests=("uv run pytest",),
    ),
    "command_injection": CategoryStrategy(
        change_type=ChangeType.SECURITY_REMEDIATION,
        base_risk=RiskLevel.HIGH,
        scope=FixScope.SINGLE_FILE,
        modification_template=(
            "Replace unsafe subprocess/shell usage with parameterized execution in {file}"
        ),
        rationale_template=(
            "Command injection vulnerabilities require removing shell=True and "
            "validating external input before execution."
        ),
        tests=("uv run pytest", "uv run semgrep --config auto {file}", "uv run bandit -r {file}"),
    ),
    "hardcoded_secret": CategoryStrategy(
        change_type=ChangeType.SECRET_REMOVAL,
        base_risk=RiskLevel.CRITICAL,
        scope=FixScope.SINGLE_FILE,
        modification_template="Remove hardcoded secret from {file} and load from environment",
        rationale_template=(
            "Secrets must be removed from source control and injected through "
            "secure runtime configuration."
        ),
        tests=("uv run gitleaks detect --source .", "uv run pytest"),
    ),
    "secret": CategoryStrategy(
        change_type=ChangeType.SECRET_REMOVAL,
        base_risk=RiskLevel.CRITICAL,
        scope=FixScope.SINGLE_FILE,
        modification_template="Remove exposed secret material from {file}",
        rationale_template="Exposed secrets must be rotated and removed from the repository.",
        tests=("uv run gitleaks detect --source .",),
    ),
    "dependency_vulnerability": CategoryStrategy(
        change_type=ChangeType.DEPENDENCY_UPDATE,
        base_risk=RiskLevel.MEDIUM,
        scope=FixScope.DEPENDENCY,
        modification_template="Upgrade vulnerable dependency in project manifest files",
        rationale_template=(
            "Dependency updates address known CVEs while preserving application behavior."
        ),
        tests=("uv run pytest", "uv run osv-scanner -r ."),
    ),
    "coverage_gap": CategoryStrategy(
        change_type=ChangeType.COVERAGE_IMPROVEMENT,
        base_risk=RiskLevel.LOW,
        scope=FixScope.SINGLE_FILE,
        modification_template="Add focused tests covering uncovered logic in {file}",
        rationale_template=(
            "Targeted regression tests reduce the chance of reintroducing defects."
        ),
        tests=("uv run pytest", "uv run coverage run -m pytest"),
    ),
}


class FixPlannerEngine:
    """Build PatchPlan objects from issue groups and their underlying findings."""

    def plan(
        self,
        run_id: str,
        issue_groups: list[IssueGroup],
        findings_by_id: dict[str, Finding],
        human_feedback_by_issue_group: dict[str, str] | None = None,
        memory_snippets: list[str] | None = None,
    ) -> list[PatchPlan]:
        plans: list[PatchPlan] = []
        now = datetime.now(UTC)
        feedback_by_group = human_feedback_by_issue_group or {}
        snippets = memory_snippets or []

        for issue_group in issue_groups:
            findings = [
                findings_by_id[finding_id]
                for finding_id in issue_group.finding_ids
                if finding_id in findings_by_id
            ]
            plan = self._build_plan(
                run_id,
                issue_group,
                findings,
                now,
                feedback_by_group.get(issue_group.issue_group_id),
                snippets,
            )
            plans.append(plan)

        return plans

    def _build_plan(
        self,
        run_id: str,
        issue_group: IssueGroup,
        findings: list[Finding],
        created_at: datetime,
        human_feedback: str | None = None,
        memory_snippets: list[str] | None = None,
    ) -> PatchPlan:
        primary_category = self._primary_category(issue_group, findings)
        strategy = CATEGORY_STRATEGIES.get(primary_category, DEFAULT_STRATEGY)
        affected_files = self._resolve_affected_files(issue_group, findings)
        scope = self._resolve_scope(strategy.scope, affected_files, primary_category)
        estimated_risk = self._estimate_risk(strategy.base_risk, findings, affected_files)
        modifications = self._build_modifications(
            strategy,
            primary_category,
            findings,
            affected_files,
        )
        expected_tests = self._build_expected_tests(strategy, affected_files)
        rollback_strategy = self._build_rollback_strategy(affected_files, estimated_risk)
        solution_rationale = self._build_rationale(strategy, issue_group, primary_category)
        if human_feedback:
            solution_rationale = (
                f"{solution_rationale} Human reviewer feedback: {human_feedback.strip()}"
            )
        if memory_snippets:
            memory_context = " ".join(memory_snippets[:3])
            solution_rationale = f"{solution_rationale} Project memory: {memory_context}"

        return PatchPlan(
            patch_plan_id=str(ObjectId()),
            run_id=run_id,
            issue_group_id=issue_group.issue_group_id,
            title=issue_group.title,
            root_cause=issue_group.root_cause,
            affected_files=affected_files,
            expected_modifications=modifications,
            expected_tests=expected_tests,
            estimated_risk=estimated_risk,
            expected_scope=scope,
            solution_rationale=solution_rationale,
            rollback_strategy=rollback_strategy,
            priority_rank=issue_group.priority_rank,
            status=PatchPlanStatus.READY,
            created_at=created_at,
        )

    @staticmethod
    def _primary_category(issue_group: IssueGroup, findings: list[Finding]) -> str:
        if issue_group.categories:
            return issue_group.categories[0]
        if findings:
            return findings[0].category
        return "unknown"

    @staticmethod
    def _resolve_affected_files(issue_group: IssueGroup, findings: list[Finding]) -> list[str]:
        files = {file_path for file_path in issue_group.affected_files if file_path}
        files.update(finding.file for finding in findings if finding.file)
        if files:
            return sorted(files)
        return ["repository"]

    @staticmethod
    def _resolve_scope(
        default_scope: FixScope,
        affected_files: list[str],
        category: str,
    ) -> FixScope:
        if category in DEPENDENCY_CATEGORIES:
            return FixScope.DEPENDENCY
        if affected_files == ["repository"]:
            return FixScope.REPOSITORY
        if len(affected_files) > 1:
            return FixScope.MULTI_FILE
        return default_scope

    @staticmethod
    def _estimate_risk(
        base_risk: RiskLevel,
        findings: list[Finding],
        affected_files: list[str],
    ) -> RiskLevel:
        risk_order = [
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
            RiskLevel.BLOCKED,
        ]
        current_index = risk_order.index(base_risk)

        if any(finding.severity == FindingSeverity.CRITICAL for finding in findings):
            current_index = max(current_index, risk_order.index(RiskLevel.CRITICAL))
        elif any(finding.severity == FindingSeverity.HIGH for finding in findings):
            current_index = max(current_index, risk_order.index(RiskLevel.HIGH))

        if any(
            marker in file_path.lower()
            for file_path in affected_files
            for marker in HIGH_RISK_FILE_MARKERS
        ):
            current_index = max(current_index, risk_order.index(RiskLevel.HIGH))

        if any(finding.category in SECRET_CATEGORIES for finding in findings):
            return RiskLevel.CRITICAL

        return risk_order[current_index]

    @staticmethod
    def _build_modifications(
        strategy: CategoryStrategy,
        category: str,
        findings: list[Finding],
        affected_files: list[str],
    ) -> list[ExpectedModification]:
        if not affected_files:
            return []

        primary_finding = findings[0] if findings else None
        tool = primary_finding.tool if primary_finding else "scanner"

        modifications: list[ExpectedModification] = []
        for file_path in affected_files:
            if file_path == "repository":
                description = strategy.modification_template.format(
                    category=category,
                    file="repository",
                    tool=tool,
                )
            else:
                description = strategy.modification_template.format(
                    category=category,
                    file=file_path,
                    tool=tool,
                )
            modifications.append(
                ExpectedModification(
                    file=file_path,
                    description=description,
                    change_type=strategy.change_type.value,
                ),
            )
        return modifications

    @staticmethod
    def _build_expected_tests(strategy: CategoryStrategy, affected_files: list[str]) -> list[str]:
        commands: list[str] = []
        primary_file = next((path for path in affected_files if path != "repository"), None)

        for test_command in strategy.tests:
            if "{file}" in test_command:
                if primary_file is None:
                    continue
                commands.append(test_command.format(file=primary_file))
            else:
                commands.append(test_command)

        return commands or ["uv run pytest"]

    @staticmethod
    def _build_rationale(
        strategy: CategoryStrategy,
        issue_group: IssueGroup,
        category: str,
    ) -> str:
        return (
            f"{strategy.rationale_template} "
            f"Issue group priority rank {issue_group.priority_rank} "
            f"covers category '{category}'."
        )

    @staticmethod
    def _build_rollback_strategy(affected_files: list[str], estimated_risk: RiskLevel) -> str:
        file_list = ", ".join(affected_files)
        if estimated_risk in {RiskLevel.CRITICAL, RiskLevel.HIGH}:
            return (
                f"Restore pre-patch copies of [{file_list}] from the run baseline snapshot "
                "and discard uncommitted working-tree changes before retrying."
            )
        return (
            f"Revert uncommitted changes in [{file_list}] using the workspace working copy "
            "or baseline snapshot if verification fails."
        )
