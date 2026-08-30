import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from app.adk.agents.diagnostic_agents import (
    AGENT_BY_NAME,
    AgentExecutionContext,
    DiagnosticAgent,
    get_diagnostic_agents,
)
from app.core.config import Settings
from app.core.logging import get_logger
from app.db.repositories.finding_repository import FindingRepository
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.intelligence import RepositoryNotReadyError
from app.models.finding import Finding
from app.models.finding_enums import DiagnosticAgentName
from app.models.run import RunStatus
from app.scanners import SubprocessCommandRunner
from app.scanners.runner import CommandRunner
from app.schemas.finding import AgentDiagnosticResult, DiagnosticAgentsResponse, FindingResponse
from app.services.run_service import RunService

logger = get_logger(__name__)

FINDINGS_ARTIFACT_NAME = "findings.json"


class DiagnosticAgentService:
    """Run diagnostic specialist agents and persist normalized findings."""

    def __init__(
        self,
        run_repository: RunRepository,
        run_service: RunService,
        finding_repository: FindingRepository,
        app_settings: Settings,
        command_runner: CommandRunner | None = None,
    ) -> None:
        self._run_repository = run_repository
        self._run_service = run_service
        self._finding_repository = finding_repository
        self._settings = app_settings
        self._command_runner = command_runner or SubprocessCommandRunner()

    def run_agents(
        self,
        user_id: str,
        run_id: str,
        agents: list[DiagnosticAgentName] | None = None,
    ) -> DiagnosticAgentsResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        repository_path = workspace.repository
        if not repository_path.exists() or not any(repository_path.iterdir()):
            raise RepositoryNotReadyError(
                "Repository must be cloned before running diagnostic agents",
            )

        self._run_repository.update_status(run_id, user_id, RunStatus.DIAGNOSING)

        started_at = datetime.now(UTC)
        output_dir = workspace.baseline / "scans"
        output_dir.mkdir(parents=True, exist_ok=True)
        context = AgentExecutionContext(
            run_id=run_id,
            repository_path=repository_path,
            output_dir=output_dir,
            command_runner=self._command_runner,
            timeout_seconds=self._settings.scanner_timeout_seconds,
        )

        selected_agents = get_diagnostic_agents(agents)
        agent_results = self._run_agents(selected_agents, context)
        findings = [finding for result in agent_results for finding in result.findings]
        persisted_findings = self._finding_repository.replace_for_run(run_id, findings)
        self._write_findings_artifact(workspace.baseline, persisted_findings)

        completed_at = datetime.now(UTC)
        finding_responses = [
            FindingResponse.model_validate(finding.model_dump()) for finding in persisted_findings
        ]
        response = DiagnosticAgentsResponse(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            agents=agent_results,
            findings=finding_responses,
            finding_count=len(persisted_findings),
        )

        logger.info(
            "Diagnostic agents completed",
            extra={
                "run_id": run_id,
                "user_id": user_id,
                "agent_count": len(agent_results),
                "finding_count": len(persisted_findings),
                "stage": "diagnostic_agents",
            },
        )
        return response

    def list_findings(self, user_id: str, run_id: str) -> list[FindingResponse]:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        findings = self._finding_repository.list_by_run(run_id)
        return [FindingResponse.model_validate(finding.model_dump()) for finding in findings]

    def execute_agent(
        self,
        user_id: str,
        run_id: str,
        agent_name: DiagnosticAgentName,
    ) -> AgentDiagnosticResult:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        repository_path = workspace.repository
        if not repository_path.exists() or not any(repository_path.iterdir()):
            raise RepositoryNotReadyError(
                "Repository must be cloned before running diagnostic agents",
            )

        output_dir = workspace.baseline / "scans"
        output_dir.mkdir(parents=True, exist_ok=True)
        context = AgentExecutionContext(
            run_id=run_id,
            repository_path=repository_path,
            output_dir=output_dir,
            command_runner=self._command_runner,
            timeout_seconds=self._settings.scanner_timeout_seconds,
        )

        agent = AGENT_BY_NAME[agent_name]
        result = self._execute_agent(agent, context)

        existing_findings = self._finding_repository.list_by_run(run_id)
        merged_findings = existing_findings + result.findings
        self._finding_repository.replace_for_run(run_id, merged_findings)
        self._write_findings_artifact(workspace.baseline, merged_findings)
        return result

    def _run_agents(
        self,
        agents: list[DiagnosticAgent],
        context: AgentExecutionContext,
    ) -> list[AgentDiagnosticResult]:
        results: list[AgentDiagnosticResult] = []

        with ThreadPoolExecutor(max_workers=len(agents)) as executor:
            futures = {
                executor.submit(self._execute_agent, agent, context): agent for agent in agents
            }
            for future in as_completed(futures):
                agent = futures[future]
                try:
                    results.append(future.result())
                except Exception:
                    logger.exception(
                        "Diagnostic agent execution failed",
                        extra={"agent": agent.name.value, "stage": "diagnostic_agents"},
                    )
                    now = datetime.now(UTC)
                    results.append(
                        AgentDiagnosticResult(
                            agent=agent.name,
                            scan_results=[],
                            findings=[],
                            started_at=now,
                            ended_at=now,
                            duration_ms=0,
                        )
                    )

        return sorted(results, key=lambda result: result.agent.value)

    @staticmethod
    def _execute_agent(
        agent: DiagnosticAgent,
        context: AgentExecutionContext,
    ) -> AgentDiagnosticResult:
        started_at = datetime.now(UTC)
        scan_results, findings = agent.run(context)
        ended_at = datetime.now(UTC)
        return AgentDiagnosticResult(
            agent=agent.name,
            scan_results=scan_results,
            findings=findings,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=int((ended_at - started_at).total_seconds() * 1000),
        )

    @staticmethod
    def _write_findings_artifact(baseline_dir: Path, findings: list[Finding]) -> Path:
        baseline_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = baseline_dir / FINDINGS_ARTIFACT_NAME
        payload = [finding.model_dump(mode="json") for finding in findings]
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return artifact_path
