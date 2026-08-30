from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ScannerTool(StrEnum):
    RUFF = "ruff"
    SEMGREP = "semgrep"
    BANDIT = "bandit"
    OSV_SCANNER = "osv_scanner"
    GITLEAKS = "gitleaks"
    PYTEST = "pytest"
    COVERAGE = "coverage"


class ScanStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"


class ScanResult(BaseModel):
    """Normalized output from a single diagnostic scanner execution."""

    tool: ScannerTool
    status: ScanStatus
    command: list[str]
    started_at: datetime
    ended_at: datetime
    duration_ms: int
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    tool_version: str | None = None
    structured_result: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


class BaselineDiagnosticsSummary(BaseModel):
    """Aggregate baseline diagnostics for a run."""

    run_id: str
    repository_path: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    scans: list[ScanResult]
