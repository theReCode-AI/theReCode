import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.models.scan import ScannerTool, ScanStatus
from app.scanners.base import RuffScanner
from app.scanners.runner import CallableCommandRunner, ProcessResult


def _process_result(
    command: list[str],
    cwd: str,
    exit_code: int,
    stdout: str = "",
) -> ProcessResult:
    now = datetime.now(UTC)
    return ProcessResult(
        command=command,
        cwd=cwd,
        exit_code=exit_code,
        stdout=stdout,
        stderr="",
        started_at=now,
        ended_at=now,
    )


def test_ruff_scanner_parses_json_issues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "main.py").write_text("x = 1\n", encoding="utf-8")

    issues = [
        {
            "filename": "main.py",
            "location": {"row": 1, "column": 1},
            "message": "unused variable",
            "code": "F841",
        }
    ]

    def handler(command: list[str], cwd: str, timeout_seconds: int) -> ProcessResult:
        del timeout_seconds
        if command[:2] == ["ruff", "--version"]:
            return _process_result(command, cwd, 0, "ruff 0.8.0")
        return _process_result(command, cwd, 1, json.dumps(issues))

    scanner = RuffScanner()
    result = scanner.run(
        repository,
        tmp_path / "output",
        CallableCommandRunner(handler),
        30,
    )

    assert result.tool == ScannerTool.RUFF
    assert result.status == ScanStatus.FAILED
    assert result.structured_result["issue_count"] == 1
    assert result.structured_result["issues"][0]["code"] == "F841"
    assert result.tool_version == "ruff 0.8.0"


def test_ruff_scanner_unavailable_when_binary_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: False)
    repository = tmp_path / "repo"
    repository.mkdir()

    scanner = RuffScanner()
    result = scanner.run(
      repository,
      tmp_path / "output",
      CallableCommandRunner(lambda *_args: _process_result([], ".", 0)),
      30,
    )

    assert result.status == ScanStatus.UNAVAILABLE
    assert result.message is not None
