import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from bson import ObjectId

from app.adk.verification.engine import VerificationEngine
from app.adk.verification.scanner_selector import select_scanners_for_plan
from app.models.fix_attempt import FixAttempt
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
from app.models.scan import ScannerTool
from app.models.verification_enums import VerificationStatus
from app.scanners.runner import CallableCommandRunner, ProcessResult


def _patch_plan(change_type: str = ChangeType.LINT_FIX.value) -> PatchPlan:
    now = datetime.now(UTC)
    return PatchPlan(
        patch_plan_id=str(ObjectId()),
        run_id="run-1",
        issue_group_id=str(ObjectId()),
        title="Lint issue",
        root_cause="Unused import",
        affected_files=["src/utils.py"],
        expected_modifications=[
            ExpectedModification(
                file="src/utils.py",
                description="Remove unused import",
                change_type=change_type,
            ),
        ],
        expected_tests=("uv run ruff check src/utils.py",),
        estimated_risk=RiskLevel.LOW,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Safe lint fix",
        rollback_strategy="Revert file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )


def _fix_attempt(status: FixAttemptStatus = FixAttemptStatus.APPLIED) -> FixAttempt:
    return FixAttempt(
        fix_attempt_id=str(ObjectId()),
        run_id="run-1",
        patch_plan_id=str(ObjectId()),
        attempt_number=1,
        status=status,
        planned_files=["src/utils.py"],
        created_at=datetime.now(UTC),
    )


def _success_runner() -> CallableCommandRunner:
    def handler(command: list[str], cwd: str, timeout_seconds: int) -> ProcessResult:
        del timeout_seconds
        now = datetime.now(UTC)
        executable = command[0]
        if command[-1] == "--version":
            return ProcessResult(command, cwd, 0, f"{executable} 1.0.0", "", now, now)
        if executable == "bash":
            return ProcessResult(command, cwd, 0, "", "", now, now)
        if executable == "ruff":
            return ProcessResult(command, cwd, 0, "[]", "", now, now)
        return ProcessResult(command, cwd, 0, "", "", now, now)

    return CallableCommandRunner(handler)


def test_select_scanners_for_lint_plan() -> None:
    tools = select_scanners_for_plan(_patch_plan())
    assert tools == [ScannerTool.RUFF]


def test_verification_skips_non_applied_attempt(tmp_path: Path) -> None:
    working = tmp_path / "working"
    working.mkdir()
    engine = VerificationEngine(_success_runner())
    result = engine.verify(working, _patch_plan(), _fix_attempt(FixAttemptStatus.SKIPPED))

    assert result.status == VerificationStatus.SKIPPED


def test_verification_passes_commands_and_scanners(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)
    working = tmp_path / "working"
    working.mkdir()
    engine = VerificationEngine(_success_runner())
    fix_attempt = _fix_attempt()

    result = engine.verify(working, _patch_plan(), fix_attempt)

    assert result.status == VerificationStatus.PASSED
    assert result.passed_checks >= 2
    assert result.failed_checks == 0


def test_verification_fails_on_command_error(tmp_path: Path) -> None:
    working = tmp_path / "working"
    working.mkdir()

    def handler(command: list[str], cwd: str, timeout_seconds: int) -> ProcessResult:
        del timeout_seconds
        now = datetime.now(UTC)
        if command[0] == "bash":
            return ProcessResult(command, cwd, 1, "", "command failed", now, now)
        if command[-1] == "--version":
            return ProcessResult(command, cwd, 0, "tool 1.0.0", "", now, now)
        return ProcessResult(command, cwd, 0, json.dumps({"results": []}), "", now, now)

    engine = VerificationEngine(CallableCommandRunner(handler))
    result = engine.verify(working, _patch_plan(), _fix_attempt())

    assert result.status == VerificationStatus.FAILED
    assert result.failed_checks >= 1
    assert result.failure_summary is not None
