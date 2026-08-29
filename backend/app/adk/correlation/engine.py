"""Deterministic finding correlation engine."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from bson import ObjectId

from app.models.finding import Finding
from app.models.finding_enums import DiagnosticAgentName, FindingSeverity
from app.models.issue_group import IssueGroup
from app.models.issue_group_enums import IssueGroupStatus

LINE_PROXIMITY_THRESHOLD = 3
SECURITY_CATEGORIES = frozenset(
    {
        "command_injection",
        "sql_injection",
        "hardcoded_secret",
        "secret",
        "security",
        "insecure_deserialization",
        "path_traversal",
        "xss",
        "authentication",
        "authorization",
    },
)
SEVERITY_WEIGHTS: dict[FindingSeverity, float] = {
    FindingSeverity.CRITICAL: 100.0,
    FindingSeverity.HIGH: 80.0,
    FindingSeverity.MEDIUM: 50.0,
    FindingSeverity.LOW: 20.0,
    FindingSeverity.INFO: 5.0,
}
SEVERITY_ORDER = (
    FindingSeverity.CRITICAL,
    FindingSeverity.HIGH,
    FindingSeverity.MEDIUM,
    FindingSeverity.LOW,
    FindingSeverity.INFO,
)


class UnionFind:
    def __init__(self, size: int) -> None:
        self._parent = list(range(size))
        self._rank = [0] * size

    def find(self, node: int) -> int:
        if self._parent[node] != node:
            self._parent[node] = self.find(self._parent[node])
        return self._parent[node]

    def union(self, left: int, right: int) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return
        if self._rank[root_left] < self._rank[root_right]:
            self._parent[root_left] = root_right
        elif self._rank[root_left] > self._rank[root_right]:
            self._parent[root_right] = root_left
        else:
            self._parent[root_right] = root_left
            self._rank[root_left] += 1


class FindingCorrelator:
    """Groups related findings, deduplicates reports, and prioritizes issues."""

    def correlate(self, run_id: str, findings: list[Finding]) -> list[IssueGroup]:
        if not findings:
            return []

        clusters = self._cluster_findings(findings)
        issue_groups: list[IssueGroup] = []
        now = datetime.now(UTC)

        for cluster_findings in clusters:
            deduped, duplicate_count = self._deduplicate_findings(cluster_findings)
            if not deduped:
                continue

            priority_score = self._calculate_priority_score(deduped, duplicate_count)
            issue_groups.append(
                IssueGroup(
                    issue_group_id=str(ObjectId()),
                    run_id=run_id,
                    title=self._build_title(deduped),
                    summary=self._build_summary(deduped, duplicate_count),
                    root_cause=self._infer_root_cause(deduped, duplicate_count),
                    finding_ids=[finding.finding_id for finding in deduped],
                    categories=sorted({finding.category for finding in deduped}),
                    agents=sorted(
                        {finding.agent for finding in deduped},
                        key=lambda agent: agent.value,
                    ),
                    tools=sorted({finding.tool for finding in deduped}),
                    severity=self._highest_severity(deduped),
                    priority_score=priority_score,
                    priority_rank=1,
                    affected_files=sorted(
                        {finding.file for finding in deduped if finding.file},
                    ),
                    duplicate_count=duplicate_count,
                    related_count=max(len(deduped) - 1, 0),
                    status=IssueGroupStatus.OPEN,
                    created_at=now,
                ),
            )

        issue_groups.sort(key=lambda group: (-group.priority_score, group.title))
        return [
            group.model_copy(update={"priority_rank": index})
            for index, group in enumerate(issue_groups, start=1)
        ]

    def _cluster_findings(self, findings: list[Finding]) -> list[list[Finding]]:
        union_find = UnionFind(len(findings))
        buckets: dict[str, list[int]] = defaultdict(list)

        for index, finding in enumerate(findings):
            for key in self._correlation_keys(finding):
                bucket = buckets[key]
                if bucket:
                    union_find.union(index, bucket[0])
                bucket.append(index)

        for left in range(len(findings)):
            for right in range(left + 1, len(findings)):
                if self._are_related(findings[left], findings[right]):
                    union_find.union(left, right)

        grouped: dict[int, list[Finding]] = defaultdict(list)
        for index, finding in enumerate(findings):
            grouped[union_find.find(index)].append(finding)

        return list(grouped.values())

    @staticmethod
    def _correlation_keys(finding: Finding) -> list[str]:
        keys: list[str] = []
        if finding.rule_id:
            keys.append(f"rule:{finding.rule_id}")
        if finding.file and finding.line_start is not None:
            line_bucket = finding.line_start // (LINE_PROXIMITY_THRESHOLD + 1)
            keys.append(f"loc:{finding.file}:{line_bucket}")
        if finding.file and finding.category:
            keys.append(f"file-category:{finding.file}:{finding.category}")
        if finding.category in SECURITY_CATEGORIES:
            keys.append(f"security:{finding.category}")
        return keys

    @staticmethod
    def _are_related(left: Finding, right: Finding) -> bool:
        if left.finding_id == right.finding_id:
            return True

        if FindingCorrelator._is_duplicate(left, right):
            return True

        if left.file and left.file == right.file:
            if left.line_start is not None and right.line_start is not None:
                if abs(left.line_start - right.line_start) <= LINE_PROXIMITY_THRESHOLD:
                    return True
            if (
                left.category in SECURITY_CATEGORIES
                and right.category in SECURITY_CATEGORIES
                and left.agent != right.agent
            ):
                return True
            if left.category == right.category:
                return True

        if left.rule_id and left.rule_id == right.rule_id:
            return True

        return False

    @staticmethod
    def _is_duplicate(left: Finding, right: Finding) -> bool:
        if left.file != right.file or left.line_start != right.line_start:
            return False
        if left.rule_id and right.rule_id and left.rule_id == right.rule_id:
            return True
        return left.category == right.category and left.message.strip() == right.message.strip()

    @staticmethod
    def _deduplicate_findings(findings: list[Finding]) -> tuple[list[Finding], int]:
        deduped: list[Finding] = []
        duplicate_count = 0
        seen_signatures: set[str] = set()

        for finding in sorted(
            findings,
            key=lambda item: (-SEVERITY_WEIGHTS[item.severity], -item.confidence),
        ):
            signature = FindingCorrelator._finding_signature(finding)
            if signature in seen_signatures:
                duplicate_count += 1
                continue
            seen_signatures.add(signature)
            deduped.append(finding)

        return deduped, duplicate_count

    @staticmethod
    def _finding_signature(finding: Finding) -> str:
        return "|".join(
            [
                finding.file or "",
                str(finding.line_start or ""),
                finding.category,
                finding.rule_id or "",
                finding.message.strip().lower(),
            ],
        )

    @staticmethod
    def _highest_severity(findings: list[Finding]) -> FindingSeverity:
        severities = {finding.severity for finding in findings}
        for severity in SEVERITY_ORDER:
            if severity in severities:
                return severity
        return FindingSeverity.INFO

    @staticmethod
    def _calculate_priority_score(findings: list[Finding], duplicate_count: int) -> float:
        max_severity = FindingCorrelator._highest_severity(findings)
        base = SEVERITY_WEIGHTS[max_severity]
        confidence_bonus = max(finding.confidence for finding in findings) * 10.0
        tool_bonus = min(15.0, float(len({finding.tool for finding in findings}) - 1) * 5.0)
        related_bonus = min(10.0, float(len(findings) - 1) * 3.0)
        duplicate_bonus = min(5.0, float(duplicate_count) * 2.0)
        score = base * 0.7 + confidence_bonus + tool_bonus + related_bonus + duplicate_bonus
        return min(100.0, score)

    @staticmethod
    def _build_title(findings: list[Finding]) -> str:
        primary = max(
            findings,
            key=lambda finding: (SEVERITY_WEIGHTS[finding.severity], finding.confidence),
        )
        location = ""
        if primary.file:
            location = f" in {primary.file}"
            if primary.line_start is not None:
                location += f":{primary.line_start}"
        return f"{primary.category.replace('_', ' ').title()}{location}"

    @staticmethod
    def _build_summary(findings: list[Finding], duplicate_count: int) -> str:
        tools = ", ".join(sorted({finding.tool for finding in findings}))
        agents = ", ".join(sorted({finding.agent.value for finding in findings}))
        parts = [
            f"{len(findings)} related finding(s) from {tools} via {agents}.",
        ]
        if duplicate_count:
            parts.append(f"{duplicate_count} duplicate report(s) were merged.")
        return " ".join(parts)

    @staticmethod
    def _infer_root_cause(findings: list[Finding], duplicate_count: int) -> str:
        agents = {finding.agent for finding in findings}
        tools = {finding.tool for finding in findings}
        categories = {finding.category for finding in findings}
        files = {finding.file for finding in findings if finding.file}

        if len(tools) > 1 and agents.intersection(
            {
                DiagnosticAgentName.SEMGREP,
                DiagnosticAgentName.SECURITY,
                DiagnosticAgentName.SECRET_CHECK,
            },
        ):
            file_label = next(iter(files)) if len(files) == 1 else "shared locations"
            return (
                f"Multiple security scanners ({', '.join(sorted(tools))}) flagged related "
                f"issues at {file_label}, indicating a shared underlying vulnerability."
            )

        if duplicate_count > 0:
            primary = findings[0]
            location = primary.file or "the repository"
            if primary.line_start is not None:
                location = f"{location}:{primary.line_start}"
            return (
                f"Duplicate reports from {', '.join(sorted(tools))} describe the same "
                f"{primary.category.replace('_', ' ')} issue at {location}."
            )

        if DiagnosticAgentName.TEST in agents and len(findings) > 1:
            return (
                "Test failures and related code findings likely share the same underlying defect."
            )

        if "test_failure" in categories:
            return "Automated tests are failing and require remediation before release."

        if "hardcoded_secret" in categories or "secret" in categories:
            return "Sensitive credentials or secrets were detected in the repository."

        primary = max(
            findings,
            key=lambda finding: (SEVERITY_WEIGHTS[finding.severity], finding.confidence),
        )
        return primary.message
