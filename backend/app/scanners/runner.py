import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


@dataclass(frozen=True)
class ProcessResult:
    command: list[str]
    cwd: str
    exit_code: int
    stdout: str
    stderr: str
    started_at: datetime
    ended_at: datetime

    @property
    def duration_ms(self) -> int:
        delta = self.ended_at - self.started_at
        return int(delta.total_seconds() * 1000)


class CommandRunner(Protocol):
    def run(
        self,
        command: list[str],
        cwd: str,
        timeout_seconds: int,
    ) -> ProcessResult: ...


class SubprocessCommandRunner:
    """Execute scanner CLI tools via subprocess."""

    def run(
        self,
        command: list[str],
        cwd: str,
        timeout_seconds: int,
    ) -> ProcessResult:
        started_at = datetime.now(UTC)
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        ended_at = datetime.now(UTC)
        return ProcessResult(
            command=command,
            cwd=cwd,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            started_at=started_at,
            ended_at=ended_at,
        )


class CallableCommandRunner:
    """Test double that delegates execution to a callable."""

    def __init__(self, handler: Callable[[list[str], str, int], ProcessResult]) -> None:
        self._handler = handler

    def run(
        self,
        command: list[str],
        cwd: str,
        timeout_seconds: int,
    ) -> ProcessResult:
        return self._handler(command, cwd, timeout_seconds)


def is_tool_available(executable: str) -> bool:
    return shutil.which(executable) is not None
