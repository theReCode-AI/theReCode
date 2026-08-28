"""Execute generated regression tests and the full pytest suite."""

from __future__ import annotations

import xml.etree.ElementTree as element_tree
from dataclasses import dataclass
from pathlib import Path

from app.adk.regression.generator import RegressionTestGenerator
from app.models.patch_plan import PatchPlan
from app.models.regression_test_enums import RegressionTestStatus
from app.scanners.runner import CommandRunner


@dataclass(frozen=True)
class RegressionExecutionResult:
    status: RegressionTestStatus
    eligible: bool
    test_file_path: str | None
    skip_reason: str | None
    targeted_exit_code: int | None
    targeted_tests: int
    targeted_passed: int
    suite_exit_code: int | None
    suite_tests: int
    suite_passed: int
    failure_summary: str | None


class RegressionTestEngine:
    """Generate, run, and summarize regression tests."""

    def __init__(
        self,
        command_runner: CommandRunner,
        timeout_seconds: int = 120,
        generator: RegressionTestGenerator | None = None,
    ) -> None:
        self._command_runner = command_runner
        self._timeout_seconds = timeout_seconds
        self._generator = generator or RegressionTestGenerator()

    def run(
        self,
        working_root: Path,
        patch_plan: PatchPlan,
        output_dir: Path,
    ) -> RegressionExecutionResult:
        generated = self._generator.generate(patch_plan)
        if not generated.eligible:
            return RegressionExecutionResult(
                status=RegressionTestStatus.SKIPPED,
                eligible=False,
                test_file_path=None,
                skip_reason=generated.skip_reason,
                targeted_exit_code=None,
                targeted_tests=0,
                targeted_passed=0,
                suite_exit_code=None,
                suite_tests=0,
                suite_passed=0,
                failure_summary=generated.skip_reason,
            )

        test_path = working_root / generated.relative_path
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(generated.content, encoding="utf-8")
        (test_path.parent / "__init__.py").touch(exist_ok=True)

        output_dir.mkdir(parents=True, exist_ok=True)
        targeted_junit = output_dir / "targeted-junit.xml"
        targeted_result = self._command_runner.run(
            [
                "pytest",
                generated.relative_path,
                "--tb=no",
                "-q",
                f"--junitxml={targeted_junit}",
            ],
            str(working_root),
            self._timeout_seconds,
        )
        targeted_summary = _parse_junit_summary(targeted_junit)

        suite_junit = output_dir / "suite-junit.xml"
        suite_result = self._command_runner.run(
            [
                "pytest",
                "--tb=no",
                "-q",
                f"--junitxml={suite_junit}",
            ],
            str(working_root),
            self._timeout_seconds,
        )
        suite_summary = _parse_junit_summary(suite_junit)

        targeted_ok = targeted_result.exit_code == 0
        suite_ok = suite_result.exit_code == 0
        if targeted_ok and suite_ok:
            status = RegressionTestStatus.PASSED
            failure_summary = None
        elif targeted_result.exit_code is None or suite_result.exit_code is None:
            status = RegressionTestStatus.ERROR
            failure_summary = _build_failure_summary(
                targeted_result.stderr or targeted_result.stdout,
                suite_result.stderr or suite_result.stdout,
            )
        else:
            status = RegressionTestStatus.FAILED
            failure_summary = _build_failure_summary(
                targeted_result.stderr or targeted_result.stdout,
                suite_result.stderr or suite_result.stdout,
            )

        return RegressionExecutionResult(
            status=status,
            eligible=True,
            test_file_path=generated.relative_path,
            skip_reason=None,
            targeted_exit_code=targeted_result.exit_code,
            targeted_tests=targeted_summary["tests"],
            targeted_passed=targeted_summary["passed"],
            suite_exit_code=suite_result.exit_code,
            suite_tests=suite_summary["tests"],
            suite_passed=suite_summary["passed"],
            failure_summary=failure_summary,
        )


def _parse_junit_summary(junit_path: Path) -> dict[str, int]:
    if not junit_path.is_file():
        return {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "passed": 0}

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


def _build_failure_summary(targeted_output: str, suite_output: str) -> str:
    parts: list[str] = []
    if targeted_output.strip():
        parts.append(f"targeted: {targeted_output.strip()[:200]}")
    if suite_output.strip():
        parts.append(f"suite: {suite_output.strip()[:200]}")
    return "; ".join(parts) if parts else "Regression test execution failed"
