from __future__ import annotations

import json
import xml.etree.ElementTree as element_tree
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.models.scan import ScannerTool, ScanResult, ScanStatus
from app.scanners.runner import CommandRunner, ProcessResult, is_tool_available


class BaseScanner(ABC):
    tool: ScannerTool
    executable: str

    @abstractmethod
    def build_command(self, repository_path: Path, output_dir: Path) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def parse_output(self, process_result: ProcessResult, output_dir: Path) -> dict[str, Any]:
        raise NotImplementedError

    def run(
        self,
        repository_path: Path,
        output_dir: Path,
        runner: CommandRunner,
        timeout_seconds: int,
    ) -> ScanResult:
        if not is_tool_available(self.executable) and self.executable != "bash":
            return self._unavailable(f"{self.executable} is not installed or not on PATH")

        command = self.build_command(repository_path, output_dir)
        process_result = runner.run(command, str(repository_path), timeout_seconds)
        tool_version = self._read_tool_version(runner, timeout_seconds)
        structured_result = self.parse_output(process_result, output_dir)
        status = self._resolve_status(process_result.exit_code, structured_result)

        return ScanResult(
            tool=self.tool,
            status=status,
            command=command,
            started_at=process_result.started_at,
            ended_at=process_result.ended_at,
            duration_ms=process_result.duration_ms,
            exit_code=process_result.exit_code,
            stdout=process_result.stdout,
            stderr=process_result.stderr,
            tool_version=tool_version,
            structured_result=structured_result,
        )

    def _read_tool_version(self, runner: CommandRunner, timeout_seconds: int) -> str | None:
        if self.executable == "bash":
            return None
        if not is_tool_available(self.executable):
            return None

        try:
            result = runner.run([self.executable, "--version"], ".", min(timeout_seconds, 30))
        except OSError:
            return None

        output = (result.stdout or result.stderr).strip()
        return output.splitlines()[0] if output else None

    @staticmethod
    def _resolve_status(exit_code: int, structured_result: dict[str, Any]) -> ScanStatus:
        if structured_result.get("skipped"):
            return ScanStatus.SKIPPED
        if exit_code == 0:
            return ScanStatus.SUCCESS
        return ScanStatus.FAILED

    def _unavailable(self, message: str) -> ScanResult:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        return ScanResult(
            tool=self.tool,
            status=ScanStatus.UNAVAILABLE,
            command=[],
            started_at=now,
            ended_at=now,
            duration_ms=0,
            message=message,
        )


def _load_json(stdout: str) -> dict[str, Any] | list[Any] | None:
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


class RuffScanner(BaseScanner):
    tool = ScannerTool.RUFF
    executable = "ruff"

    def build_command(self, repository_path: Path, output_dir: Path) -> list[str]:
        del repository_path, output_dir
        return [self.executable, "check", ".", "--output-format", "json"]

    def parse_output(self, process_result: ProcessResult, output_dir: Path) -> dict[str, Any]:
        del output_dir
        payload = _load_json(process_result.stdout)
        issues = payload if isinstance(payload, list) else []
        return {
            "issue_count": len(issues),
            "issues": issues,
        }


class SemgrepScanner(BaseScanner):
    tool = ScannerTool.SEMGREP
    executable = "semgrep"

    def build_command(self, repository_path: Path, output_dir: Path) -> list[str]:
        del output_dir
        return [
            self.executable,
            "scan",
            "--config",
            "auto",
            "--json",
            "--quiet",
            str(repository_path),
        ]

    def parse_output(self, process_result: ProcessResult, output_dir: Path) -> dict[str, Any]:
        del output_dir
        payload = _load_json(process_result.stdout)
        if not isinstance(payload, dict):
            return {"issue_count": 0, "results": []}

        results = payload.get("results", [])
        return {
            "issue_count": len(results) if isinstance(results, list) else 0,
            "results": results,
            "errors": payload.get("errors", []),
        }


class BanditScanner(BaseScanner):
    tool = ScannerTool.BANDIT
    executable = "bandit"

    def build_command(self, repository_path: Path, output_dir: Path) -> list[str]:
        del repository_path, output_dir
        return [self.executable, "-r", ".", "-f", "json", "-q"]

    def parse_output(self, process_result: ProcessResult, output_dir: Path) -> dict[str, Any]:
        del output_dir
        payload = _load_json(process_result.stdout)
        if not isinstance(payload, dict):
            return {"issue_count": 0, "results": [], "metrics": {}}

        results = payload.get("results", [])
        return {
            "issue_count": len(results) if isinstance(results, list) else 0,
            "results": results,
            "metrics": payload.get("metrics", {}),
        }


class OsvScanner(BaseScanner):
    tool = ScannerTool.OSV_SCANNER
    executable = "osv-scanner"

    def build_command(self, repository_path: Path, output_dir: Path) -> list[str]:
        del output_dir
        return [self.executable, "--recursive", "--format", "json", str(repository_path)]

    def parse_output(self, process_result: ProcessResult, output_dir: Path) -> dict[str, Any]:
        del output_dir
        payload = _load_json(process_result.stdout)
        if not isinstance(payload, dict):
            return {"vulnerability_count": 0, "results": []}

        results = payload.get("results", [])
        vulnerability_count = 0
        if isinstance(results, list):
            for package_result in results:
                vulnerabilities = package_result.get("vulnerabilities", [])
                if isinstance(vulnerabilities, list):
                    vulnerability_count += len(vulnerabilities)

        return {
            "vulnerability_count": vulnerability_count,
            "results": results,
        }


class GitleaksScanner(BaseScanner):
    tool = ScannerTool.GITLEAKS
    executable = "gitleaks"

    def build_command(self, repository_path: Path, output_dir: Path) -> list[str]:
        report_path = output_dir / "gitleaks-report.json"
        return [
            self.executable,
            "detect",
            "--source",
            str(repository_path),
            "--report-format",
            "json",
            "--report-path",
            str(report_path),
            "--no-git",
        ]

    def parse_output(self, process_result: ProcessResult, output_dir: Path) -> dict[str, Any]:
        report_path = output_dir / "gitleaks-report.json"
        if report_path.is_file():
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            findings = payload if isinstance(payload, list) else []
            return {
                "finding_count": len(findings),
                "findings": findings,
            }

        payload = _load_json(process_result.stdout)
        findings = payload if isinstance(payload, list) else []
        return {
            "finding_count": len(findings),
            "findings": findings,
        }


class PytestScanner(BaseScanner):
    tool = ScannerTool.PYTEST
    executable = "pytest"

    def build_command(self, repository_path: Path, output_dir: Path) -> list[str]:
        del repository_path
        junit_path = output_dir / "pytest-results.xml"
        return [
            self.executable,
            "--tb=no",
            "-q",
            f"--junitxml={junit_path}",
        ]

    def parse_output(self, process_result: ProcessResult, output_dir: Path) -> dict[str, Any]:
        junit_path = output_dir / "pytest-results.xml"
        summary = _parse_junit_summary(junit_path)
        summary["stdout"] = process_result.stdout.strip()
        return summary


class CoverageScanner(BaseScanner):
    tool = ScannerTool.COVERAGE
    executable = "coverage"

    def run(
        self,
        repository_path: Path,
        output_dir: Path,
        runner: CommandRunner,
        timeout_seconds: int,
    ) -> ScanResult:
        if not is_tool_available("coverage") or not is_tool_available("pytest"):
            return self._unavailable("coverage and pytest must be installed and on PATH")
        return super().run(repository_path, output_dir, runner, timeout_seconds)

    def build_command(self, repository_path: Path, output_dir: Path) -> list[str]:
        del repository_path
        json_path = output_dir / "coverage.json"
        return [
            "bash",
            "-lc",
            f"coverage run -m pytest --tb=no -q && coverage json -o {json_path}",
        ]

    def parse_output(self, process_result: ProcessResult, output_dir: Path) -> dict[str, Any]:
        json_path = output_dir / "coverage.json"
        if not json_path.is_file():
            return {
                "skipped": process_result.exit_code != 0,
                "percent_covered": None,
                "totals": {},
            }

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        totals = payload.get("totals", {}) if isinstance(payload, dict) else {}
        return {
            "percent_covered": totals.get("percent_covered"),
            "totals": totals,
            "files": payload.get("files", {}) if isinstance(payload, dict) else {},
        }


def _parse_junit_summary(junit_path: Path) -> dict[str, Any]:
    if not junit_path.is_file():
        return {
            "tests": 0,
            "failures": 0,
            "errors": 0,
            "skipped": 0,
            "passed": 0,
        }

    root = element_tree.parse(junit_path).getroot()
    if root.tag == "testsuites":
        tests = failures = errors = skipped = 0
        for suite in root.findall("testsuite"):
            tests += int(suite.attrib.get("tests", 0))
            failures += int(suite.attrib.get("failures", 0))
            errors += int(suite.attrib.get("errors", 0))
            skipped += int(suite.attrib.get("skipped", 0))
    else:
        tests = int(root.attrib.get("tests", 0))
        failures = int(root.attrib.get("failures", 0))
        errors = int(root.attrib.get("errors", 0))
        skipped = int(root.attrib.get("skipped", 0))

    passed = max(tests - failures - errors - skipped, 0)
    return {
        "tests": tests,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "passed": passed,
    }
