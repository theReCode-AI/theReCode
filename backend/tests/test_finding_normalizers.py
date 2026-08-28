from datetime import UTC, datetime

from app.adk.normalizers import normalize_scan_results
from app.models.finding_enums import DiagnosticAgentName, FindingSeverity
from app.models.scan import ScannerTool, ScanResult, ScanStatus


def _scan_result(tool: ScannerTool, structured_result: dict) -> ScanResult:
    now = datetime.now(UTC)
    return ScanResult(
        tool=tool,
        status=ScanStatus.SUCCESS,
        command=[tool.value],
        started_at=now,
        ended_at=now,
        duration_ms=1,
        structured_result=structured_result,
    )


def test_normalize_ruff_findings() -> None:
    scan_result = _scan_result(
        ScannerTool.RUFF,
        {
            "issues": [
                {
                    "filename": "src/main.py",
                    "location": {"row": 10, "column": 1},
                    "message": "unused variable",
                    "code": "F841",
                }
            ]
        },
    )

    findings = normalize_scan_results(
        DiagnosticAgentName.CODE_QUALITY,
        "64f0a1b2c3d4e5f678901234",
        [scan_result],
    )

    assert len(findings) == 1
    assert findings[0].tool == "ruff"
    assert findings[0].severity == FindingSeverity.LOW
    assert findings[0].file == "src/main.py"
    assert findings[0].line_start == 10
    assert findings[0].rule_id == "F841"


def test_normalize_gitleaks_redacts_secret_evidence() -> None:
    scan_result = _scan_result(
        ScannerTool.GITLEAKS,
        {
            "findings": [
                {
                    "File": "config.py",
                    "StartLine": 3,
                    "EndLine": 3,
                    "Description": "AWS Key",
                    "RuleID": "aws-access-key",
                    "Match": "api_key=super-secret-value",
                }
            ]
        },
    )

    findings = normalize_scan_results(
        DiagnosticAgentName.SECRET_CHECK,
        "64f0a1b2c3d4e5f678901234",
        [scan_result],
    )

    assert len(findings) == 1
    assert findings[0].severity == FindingSeverity.CRITICAL
    assert findings[0].evidence == "api_key=***REDACTED***"


def test_normalize_pytest_emits_failure_finding() -> None:
    scan_result = _scan_result(
        ScannerTool.PYTEST,
        {"failures": 2, "errors": 1, "stdout": "2 failed"},
    )

    findings = normalize_scan_results(
        DiagnosticAgentName.TEST,
        "64f0a1b2c3d4e5f678901234",
        [scan_result],
    )

    assert len(findings) == 1
    assert findings[0].category == "test_failure"
    assert "2 failure" in findings[0].message
