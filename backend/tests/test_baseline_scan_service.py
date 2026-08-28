import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from bson import ObjectId

from app.core.config import Settings
from app.db.repositories.run_repository import RunNotFoundError
from app.intelligence import RepositoryNotReadyError
from app.models.run import RunStatus
from app.models.scan import ScannerTool, ScanStatus
from app.scanners.runner import CallableCommandRunner, ProcessResult
from app.schemas.project import ProjectCreate
from app.schemas.run import RunCreate
from app.services.baseline_scan_service import (
    BASELINE_SUMMARY_NAME,
    BaselineDiagnosticsNotFoundError,
    BaselineScanService,
)
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.workspace import WorkspaceManager
from tests.test_project_intelligence_inspector import SAMPLE_FASTAPI_PROJECT
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_run_service import InMemoryRunRepository


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


@pytest.fixture
def baseline_service(tmp_path: Path):
    project_repository = InMemoryProjectRepository()
    linked_repository_repository = InMemoryLinkedRepositoryRepository()
    run_repository = InMemoryRunRepository()
    project_service = ProjectService(project_repository, linked_repository_repository)
    workspace_manager = WorkspaceManager(tmp_path)
    run_service = RunService(run_repository, project_service, workspace_manager)
    settings = Settings(environment="test", scanner_timeout_seconds=30)

    def handler(command: list[str], cwd: str, timeout_seconds: int) -> ProcessResult:
        del timeout_seconds
        executable = command[0]
        if executable.endswith("version") or command[-1] == "--version":
            return _process_result(command, cwd, 0, f"{executable} 1.0.0")
        if executable == "ruff":
            return _process_result(command, cwd, 0, "[]")
        if executable == "semgrep":
            return _process_result(command, cwd, 0, json.dumps({"results": []}))
        if executable == "bandit":
            return _process_result(command, cwd, 0, json.dumps({"results": [], "metrics": {}}))
        if executable == "osv-scanner":
            return _process_result(command, cwd, 0, json.dumps({"results": []}))
        if executable == "gitleaks":
            report_flag_index = command.index("--report-path")
            report_path = Path(command[report_flag_index + 1])
            report_path.write_text("[]", encoding="utf-8")
            return _process_result(command, cwd, 0)
        if executable == "pytest":
            junit_flag = next(arg for arg in command if arg.startswith("--junitxml="))
            junit_path = Path(junit_flag.split("=", 1)[1])
            junit_path.write_text(
                '<testsuite tests="2" failures="0" errors="0" skipped="0"></testsuite>',
                encoding="utf-8",
            )
            return _process_result(command, cwd, 0, "2 passed")
        if executable == "bash":
            json_flag = command[-1]
            if "coverage json" in json_flag:
                output_path = json_flag.rsplit(" ", 1)[-1]
                Path(output_path).write_text(
                    json.dumps({"totals": {"percent_covered": 88.5}, "files": {}}),
                    encoding="utf-8",
                )
            return _process_result(command, cwd, 0)
        return _process_result(command, cwd, 0)

    service = BaselineScanService(
        run_repository=run_repository,
        run_service=run_service,
        app_settings=settings,
        command_runner=CallableCommandRunner(handler),
    )
    return service, run_service, project_service, workspace_manager, run_repository


def _seed_repository(workspace_manager: WorkspaceManager, run_id: str) -> None:
    workspace = workspace_manager.get_run_workspace(run_id)
    shutil.copytree(
        SAMPLE_FASTAPI_PROJECT,
        workspace.repository,
        dirs_exist_ok=True,
    )


def test_run_diagnostics_persists_summary(
    baseline_service,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, run_service, project_service, workspace_manager, run_repository = baseline_service
    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Diagnostics Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    _seed_repository(workspace_manager, run.id)

    result = service.run_diagnostics(user_id, run.id, tools=[ScannerTool.RUFF, ScannerTool.PYTEST])

    assert result.run_id == run.id
    assert len(result.scans) == 2
    assert all(scan.status in {ScanStatus.SUCCESS, ScanStatus.FAILED} for scan in result.scans)

    workspace = workspace_manager.get_run_workspace(run.id)
    summary_path = workspace.baseline / BASELINE_SUMMARY_NAME
    assert summary_path.is_file()
    assert (workspace.baseline / "scans" / "ruff.json").is_file()

    stored_run = run_repository.get_by_id_for_user(run.id, user_id)
    assert stored_run is not None
    assert stored_run.status == RunStatus.DIAGNOSING


def test_run_diagnostics_requires_repository(baseline_service) -> None:
    service, run_service, project_service, _, _ = baseline_service
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Empty Repo Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    with pytest.raises(RepositoryNotReadyError):
        service.run_diagnostics(user_id, run.id)


def test_get_diagnostics_not_found(baseline_service) -> None:
    service, run_service, project_service, _, _ = baseline_service
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Missing Diagnostics"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    with pytest.raises(RunNotFoundError):
        service.get_diagnostics(str(ObjectId()), run.id)

    with pytest.raises(BaselineDiagnosticsNotFoundError):
        service.get_diagnostics(user_id, run.id)
