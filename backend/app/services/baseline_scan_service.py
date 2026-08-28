import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.intelligence import RepositoryNotReadyError
from app.models.run import RunStatus
from app.models.scan import BaselineDiagnosticsSummary, ScannerTool, ScanResult, ScanStatus
from app.scanners import SubprocessCommandRunner, get_scanners
from app.scanners.base import BaseScanner
from app.scanners.runner import CommandRunner
from app.schemas.scan import BaselineDiagnosticsResponse
from app.services.run_service import RunService

logger = get_logger(__name__)

BASELINE_SUMMARY_NAME = "baseline_diagnostics.json"


class BaselineDiagnosticsNotFoundError(Exception):
    def __init__(
        self,
        message: str = "Baseline diagnostics are not available for this run",
    ) -> None:
        self.message = message
        super().__init__(message)


class BaselineScanService:
    """Run baseline diagnostic scanners against a cloned repository."""

    def __init__(
        self,
        run_repository: RunRepository,
        run_service: RunService,
        app_settings: Settings,
        command_runner: CommandRunner | None = None,
    ) -> None:
        self._run_repository = run_repository
        self._run_service = run_service
        self._settings = app_settings
        self._command_runner = command_runner or SubprocessCommandRunner()

    def run_diagnostics(
        self,
        user_id: str,
        run_id: str,
        tools: list[ScannerTool] | None = None,
    ) -> BaselineDiagnosticsResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        repository_path = workspace.repository
        if not repository_path.exists() or not any(repository_path.iterdir()):
            raise RepositoryNotReadyError("Repository must be cloned before running diagnostics")

        self._run_repository.update_status(run_id, user_id, RunStatus.DIAGNOSING)

        started_at = datetime.now(UTC)
        output_dir = workspace.baseline / "scans"
        output_dir.mkdir(parents=True, exist_ok=True)

        scanners = get_scanners(tools)
        scan_results = self._run_scanners(scanners, repository_path, output_dir)
        completed_at = datetime.now(UTC)

        summary = BaselineDiagnosticsSummary(
            run_id=run_id,
            repository_path=str(repository_path),
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            scans=scan_results,
        )

        self._write_summary(workspace.baseline, summary)
        self._write_individual_scans(output_dir, scan_results)

        logger.info(
            "Baseline diagnostics completed",
            extra={
                "run_id": run_id,
                "user_id": user_id,
                "scanner_count": len(scan_results),
                "stage": "baseline_diagnostics",
            },
        )

        self._run_repository.update_status(run_id, user_id, RunStatus.DIAGNOSING)

        return BaselineDiagnosticsResponse.model_validate(summary.model_dump())

    def get_diagnostics(self, user_id: str, run_id: str) -> BaselineDiagnosticsResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        summary_path = workspace.baseline / BASELINE_SUMMARY_NAME
        if not summary_path.is_file():
            raise BaselineDiagnosticsNotFoundError()

        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        return BaselineDiagnosticsResponse.model_validate(payload)

    def _run_scanners(
        self,
        scanners: list[BaseScanner],
        repository_path: Path,
        output_dir: Path,
    ) -> list[ScanResult]:
        timeout_seconds = self._settings.scanner_timeout_seconds
        results: list[ScanResult] = []

        with ThreadPoolExecutor(max_workers=len(scanners)) as executor:
            futures = {
                executor.submit(
                    scanner.run,
                    repository_path,
                    output_dir,
                    self._command_runner,
                    timeout_seconds,
                ): scanner
                for scanner in scanners
            }
            for future in as_completed(futures):
                scanner = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    logger.exception(
                        "Scanner execution failed",
                        extra={"tool": scanner.tool.value, "stage": "baseline_diagnostics"},
                    )
                    results.append(self._failed_scan_result(scanner.tool, str(exc)))

        return sorted(results, key=lambda result: result.tool.value)

    @staticmethod
    def _failed_scan_result(tool: ScannerTool, message: str) -> ScanResult:
        now = datetime.now(UTC)
        return ScanResult(
            tool=tool,
            status=ScanStatus.FAILED,
            command=[],
            started_at=now,
            ended_at=now,
            duration_ms=0,
            message=message,
        )

    @staticmethod
    def _write_summary(baseline_dir: Path, summary: BaselineDiagnosticsSummary) -> Path:
        baseline_dir.mkdir(parents=True, exist_ok=True)
        summary_path = baseline_dir / BASELINE_SUMMARY_NAME
        summary_path.write_text(
            json.dumps(summary.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return summary_path

    @staticmethod
    def _write_individual_scans(output_dir: Path, scan_results: list[ScanResult]) -> None:
        for scan_result in scan_results:
            scan_path = output_dir / f"{scan_result.tool.value}.json"
            scan_path.write_text(
                json.dumps(scan_result.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
