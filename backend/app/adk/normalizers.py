from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.models.finding import Finding
from app.models.finding_enums import (
    DiagnosticAgentName,
    FindingFixability,
    FindingSeverity,
    FindingStatus,
)
from app.models.scan import ScannerTool, ScanResult

SECRET_EVIDENCE_PATTERN = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|passwd|credential)\s*[:=]\s*\S+",
)


def normalize_scan_results(
    agent: DiagnosticAgentName,
    run_id: str,
    scan_results: list[ScanResult],
) -> list[Finding]:
    findings: list[Finding] = []
    for scan_result in scan_results:
        normalizer = NORMALIZERS.get(scan_result.tool)
        if normalizer is None:
            continue
        findings.extend(normalizer(agent, run_id, scan_result))
    return findings


def _build_finding(
    *,
    run_id: str,
    agent: DiagnosticAgentName,
    tool: str,
    category: str,
    severity: FindingSeverity,
    message: str,
    confidence: float = 0.9,
    file: str | None = None,
    line_start: int | None = None,
    line_end: int | None = None,
    rule_id: str | None = None,
    evidence: str | None = None,
    fixability: FindingFixability = FindingFixability.AGENT,
) -> Finding:
    dedupe_key = "|".join(
        [
            run_id,
            agent.value,
            tool,
            category,
            file or "",
            str(line_start or ""),
            str(line_end or ""),
            rule_id or "",
            message,
        ]
    )
    finding_id = hashlib.sha256(dedupe_key.encode()).hexdigest()[:24]
    if not ObjectId.is_valid(finding_id):
        finding_id = str(ObjectId())

    return Finding(
        finding_id=finding_id,
        run_id=run_id,
        agent=agent,
        tool=tool,
        category=category,
        severity=severity,
        confidence=confidence,
        file=file,
        line_start=line_start,
        line_end=line_end,
        message=message,
        rule_id=rule_id,
        evidence=_redact_evidence(evidence),
        fixability=fixability,
        status=FindingStatus.OPEN,
        created_at=datetime.now(UTC),
    )


def _redact_evidence(evidence: str | None) -> str | None:
    if evidence is None:
        return None
    return SECRET_EVIDENCE_PATTERN.sub(r"\1=***REDACTED***", evidence)


def _map_bandit_severity(value: str | None) -> FindingSeverity:
    mapping = {
        "LOW": FindingSeverity.LOW,
        "MEDIUM": FindingSeverity.MEDIUM,
        "HIGH": FindingSeverity.HIGH,
    }
    return mapping.get((value or "").upper(), FindingSeverity.MEDIUM)


def _map_semgrep_severity(value: str | None) -> FindingSeverity:
    mapping = {
        "INFO": FindingSeverity.INFO,
        "WARNING": FindingSeverity.MEDIUM,
        "ERROR": FindingSeverity.HIGH,
    }
    return mapping.get((value or "").upper(), FindingSeverity.MEDIUM)


def _normalize_ruff(
    agent: DiagnosticAgentName,
    run_id: str,
    scan_result: ScanResult,
) -> list[Finding]:
    issues = scan_result.structured_result.get("issues", [])
    if not isinstance(issues, list):
        return []

    findings: list[Finding] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        location = issue.get("location", {})
        findings.append(
            _build_finding(
                run_id=run_id,
                agent=agent,
                tool=scan_result.tool.value,
                category="code_quality",
                severity=FindingSeverity.LOW,
                message=str(issue.get("message", "Ruff issue detected")),
                file=str(issue.get("filename")) if issue.get("filename") else None,
                line_start=_safe_int(location.get("row")),
                line_end=_safe_int(location.get("row")),
                rule_id=str(issue.get("code")) if issue.get("code") else None,
                evidence=str(issue.get("message")),
            )
        )
    return findings


def _normalize_semgrep(
    agent: DiagnosticAgentName,
    run_id: str,
    scan_result: ScanResult,
) -> list[Finding]:
    results = scan_result.structured_result.get("results", [])
    if not isinstance(results, list):
        return []

    findings: list[Finding] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        extra = result.get("extra", {})
        if not isinstance(extra, dict):
            extra = {}
        metadata = extra.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        start = result.get("start", {})
        end = result.get("end", {})
        findings.append(
            _build_finding(
                run_id=run_id,
                agent=agent,
                tool=scan_result.tool.value,
                category=str(metadata.get("category", "security")),
                severity=_map_semgrep_severity(str(extra.get("severity"))),
                message=str(extra.get("message", "Semgrep finding")),
                file=str(result.get("path")) if result.get("path") else None,
                line_start=_safe_int(start.get("line") if isinstance(start, dict) else None),
                line_end=_safe_int(end.get("line") if isinstance(end, dict) else None),
                rule_id=str(result.get("check_id")) if result.get("check_id") else None,
                evidence=str(extra.get("lines")),
            )
        )
    return findings


def _normalize_bandit(
    agent: DiagnosticAgentName,
    run_id: str,
    scan_result: ScanResult,
) -> list[Finding]:
    results = scan_result.structured_result.get("results", [])
    if not isinstance(results, list):
        return []

    findings: list[Finding] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        findings.append(
            _build_finding(
                run_id=run_id,
                agent=agent,
                tool=scan_result.tool.value,
                category="security",
                severity=_map_bandit_severity(str(result.get("issue_severity"))),
                message=str(result.get("issue_text", "Bandit security issue")),
                file=str(result.get("filename")) if result.get("filename") else None,
                line_start=_safe_int(result.get("line_number")),
                line_end=_safe_int(result.get("line_number")),
                rule_id=str(result.get("test_id")) if result.get("test_id") else None,
                evidence=str(result.get("code")),
            )
        )
    return findings


def _normalize_osv(
    agent: DiagnosticAgentName,
    run_id: str,
    scan_result: ScanResult,
) -> list[Finding]:
    results = scan_result.structured_result.get("results", [])
    if not isinstance(results, list):
        return []

    findings: list[Finding] = []
    for package_result in results:
        if not isinstance(package_result, dict):
            continue
        package_name = package_result.get("package", {}).get("name", "unknown")
        vulnerabilities = package_result.get("vulnerabilities", [])
        if not isinstance(vulnerabilities, list):
            continue
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict):
                continue
            findings.append(
                _build_finding(
                    run_id=run_id,
                    agent=agent,
                    tool=scan_result.tool.value,
                    category="dependency_vulnerability",
                    severity=FindingSeverity.HIGH,
                    message=str(vulnerability.get("summary", "Dependency vulnerability detected")),
                    rule_id=str(vulnerability.get("id")) if vulnerability.get("id") else None,
                    evidence=f"package={package_name}",
                    fixability=FindingFixability.MANUAL,
                )
            )
    return findings


def _normalize_gitleaks(
    agent: DiagnosticAgentName,
    run_id: str,
    scan_result: ScanResult,
) -> list[Finding]:
    raw_findings = scan_result.structured_result.get("findings", [])
    if not isinstance(raw_findings, list):
        return []

    findings: list[Finding] = []
    for result in raw_findings:
        if not isinstance(result, dict):
            continue
        findings.append(
            _build_finding(
                run_id=run_id,
                agent=agent,
                tool=scan_result.tool.value,
                category="secret_exposure",
                severity=FindingSeverity.CRITICAL,
                message=str(result.get("Description", "Potential secret detected")),
                file=str(result.get("File")) if result.get("File") else None,
                line_start=_safe_int(result.get("StartLine")),
                line_end=_safe_int(result.get("EndLine")),
                rule_id=str(result.get("RuleID")) if result.get("RuleID") else None,
                evidence=str(result.get("Match")),
                fixability=FindingFixability.MANUAL,
                confidence=0.98,
            )
        )
    return findings


def _normalize_pytest(
    agent: DiagnosticAgentName,
    run_id: str,
    scan_result: ScanResult,
) -> list[Finding]:
    failures = _safe_int(scan_result.structured_result.get("failures")) or 0
    errors = _safe_int(scan_result.structured_result.get("errors")) or 0
    if failures == 0 and errors == 0:
        return []

    return [
        _build_finding(
            run_id=run_id,
            agent=agent,
            tool=scan_result.tool.value,
            category="test_failure",
            severity=FindingSeverity.HIGH,
            message=(
                f"Pytest reported {failures} failure(s) and {errors} error(s)"
            ),
            evidence=scan_result.structured_result.get("stdout"),
            fixability=FindingFixability.AGENT,
        )
    ]


def _normalize_coverage(
    agent: DiagnosticAgentName,
    run_id: str,
    scan_result: ScanResult,
) -> list[Finding]:
    percent_covered = scan_result.structured_result.get("percent_covered")
    if percent_covered is None:
        return []

    coverage_value = float(percent_covered)
    if coverage_value >= 80.0:
        return []

    return [
        _build_finding(
            run_id=run_id,
            agent=agent,
            tool=scan_result.tool.value,
            category="test_coverage",
            severity=FindingSeverity.MEDIUM,
            message=f"Project coverage is {coverage_value:.1f}%",
            evidence=str(scan_result.structured_result.get("totals", {})),
            fixability=FindingFixability.MANUAL,
            confidence=0.85,
        )
    ]


def _safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


NORMALIZERS = {
    ScannerTool.RUFF: _normalize_ruff,
    ScannerTool.SEMGREP: _normalize_semgrep,
    ScannerTool.BANDIT: _normalize_bandit,
    ScannerTool.OSV_SCANNER: _normalize_osv,
    ScannerTool.GITLEAKS: _normalize_gitleaks,
    ScannerTool.PYTEST: _normalize_pytest,
    ScannerTool.COVERAGE: _normalize_coverage,
}
