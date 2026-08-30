"""Deterministic verification engine for applied fixes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.adk.verification.scanner_selector import select_scanners_for_plan
from app.models.fix_attempt import FixAttempt
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.patch_plan import PatchPlan
from app.models.scan import ScanResult, ScanStatus
from app.models.verification_enums import (
    VerificationCheckStatus,
    VerificationCheckType,
    VerificationStatus,
)
from app.models.verification_result import VerificationCheck
from app.scanners.registry import get_scanners
from app.scanners.runner import CommandRunner


@dataclass(frozen=True)
class VerificationRunResult:
    status: VerificationStatus
    checks: list[VerificationCheck]
    passed_checks: int
    failed_checks: int
    skipped_checks: int
    failure_summary: str | None
    scan_results: list[ScanResult]


class VerificationEngine:
    """Validate applied fixes using patch-plan tests and targeted scanners."""

    def __init__(self, command_runner: CommandRunner, timeout_seconds: int = 120) -> None:
        self._command_runner = command_runner
        self._timeout_seconds = timeout_seconds

    def verify(
        self,
        working_root: Path,
        patch_plan: PatchPlan,
        fix_attempt: FixAttempt,
    ) -> VerificationRunResult:
        if fix_attempt.status != FixAttemptStatus.APPLIED:
            return VerificationRunResult(
                status=VerificationStatus.SKIPPED,
                checks=[],
                passed_checks=0,
                failed_checks=0,
                skipped_checks=0,
                failure_summary="Fix attempt was not applied",
                scan_results=[],
            )

        if not working_root.is_dir():
            return VerificationRunResult(
                status=VerificationStatus.ERROR,
                checks=[],
                passed_checks=0,
                failed_checks=0,
                skipped_checks=0,
                failure_summary="Working copy is not available for verification",
                scan_results=[],
            )

        checks: list[VerificationCheck] = []
        scan_results: list[ScanResult] = []

        for command in patch_plan.expected_tests:
            checks.append(self._run_command_check(command, working_root))

        output_dir = working_root.parent / "baseline" / "verification" / fix_attempt.fix_attempt_id
        output_dir.mkdir(parents=True, exist_ok=True)

        scanners = get_scanners(select_scanners_for_plan(patch_plan))
        for scanner in scanners:
            scan_result = scanner.run(
                working_root,
                output_dir,
                self._command_runner,
                self._timeout_seconds,
            )
            scan_results.append(scan_result)
            checks.append(self._scan_result_to_check(scan_result))

        passed_checks = sum(
            1 for check in checks if check.status == VerificationCheckStatus.PASSED
        )
        failed_checks = sum(
            1 for check in checks if check.status == VerificationCheckStatus.FAILED
        )
        skipped_checks = sum(
            1 for check in checks if check.status == VerificationCheckStatus.SKIPPED
        )

        if failed_checks > 0:
            status = VerificationStatus.FAILED
            failure_summary = _build_failure_summary(checks)
        elif any(check.status == VerificationCheckStatus.ERROR for check in checks):
            status = VerificationStatus.ERROR
            failure_summary = _build_failure_summary(checks)
        else:
            status = VerificationStatus.PASSED
            failure_summary = None

        return VerificationRunResult(
            status=status,
            checks=checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            skipped_checks=skipped_checks,
            failure_summary=failure_summary,
            scan_results=scan_results,
        )

    def _run_command_check(self, command: str, working_root: Path) -> VerificationCheck:
        if not command.strip():
            return VerificationCheck(
                check_type=VerificationCheckType.COMMAND,
                name=command,
                status=VerificationCheckStatus.SKIPPED,
                message="Empty verification command",
            )

        try:
            process_result = self._command_runner.run(
                ["bash", "-lc", command],
                str(working_root),
                self._timeout_seconds,
            )
        except OSError as exc:
            return VerificationCheck(
                check_type=VerificationCheckType.COMMAND,
                name=command,
                status=VerificationCheckStatus.ERROR,
                message=str(exc),
            )

        status = (
            VerificationCheckStatus.PASSED
            if process_result.exit_code == 0
            else VerificationCheckStatus.FAILED
        )
        message = process_result.stderr or process_result.stdout or None
        if status == VerificationCheckStatus.FAILED and not message:
            message = f"Command exited with code {process_result.exit_code}"

        return VerificationCheck(
            check_type=VerificationCheckType.COMMAND,
            name=command,
            status=status,
            exit_code=process_result.exit_code,
            message=message,
            duration_ms=process_result.duration_ms,
        )

    @staticmethod
    def _scan_result_to_check(scan_result: ScanResult) -> VerificationCheck:
        if scan_result.status == ScanStatus.SUCCESS:
            status = VerificationCheckStatus.PASSED
        elif scan_result.status == ScanStatus.SKIPPED:
            status = VerificationCheckStatus.SKIPPED
        elif scan_result.status == ScanStatus.UNAVAILABLE:
            status = VerificationCheckStatus.SKIPPED
        else:
            status = VerificationCheckStatus.FAILED

        message = scan_result.message
        if status == VerificationCheckStatus.FAILED and not message:
            message = scan_result.stderr or scan_result.stdout or "Scanner reported failure"

        return VerificationCheck(
            check_type=VerificationCheckType.SCANNER,
            name=scan_result.tool.value,
            status=status,
            exit_code=scan_result.exit_code,
            message=message,
            duration_ms=scan_result.duration_ms,
        )


def _build_failure_summary(checks: list[VerificationCheck]) -> str:
    failed_checks = [
        check
        for check in checks
        if check.status in {VerificationCheckStatus.FAILED, VerificationCheckStatus.ERROR}
    ]
    if not failed_checks:
        return "Verification failed"

    summaries = []
    for check in failed_checks[:5]:
        label = check.name
        detail = check.message or check.status.value
        summaries.append(f"{label}: {detail}")

    return "; ".join(summaries)
