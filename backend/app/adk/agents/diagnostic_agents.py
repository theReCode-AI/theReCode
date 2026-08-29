from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.adk.normalizers import normalize_scan_results
from app.models.finding import Finding
from app.models.finding_enums import DiagnosticAgentName
from app.models.scan import ScannerTool, ScanResult
from app.scanners.registry import SCANNER_BY_TOOL
from app.scanners.runner import CommandRunner


@dataclass(frozen=True)
class AgentExecutionContext:
    run_id: str
    repository_path: Path
    output_dir: Path
    command_runner: CommandRunner
    timeout_seconds: int


class DiagnosticAgent(ABC):
    """ADK-ready specialist agent that runs scanners and emits normalized findings."""

    name: DiagnosticAgentName

    @abstractmethod
    def scanner_tools(self) -> tuple[ScannerTool, ...]:
        raise NotImplementedError

    def run(self, context: AgentExecutionContext) -> tuple[list[ScanResult], list[Finding]]:
        started_at = datetime.now(UTC)
        scan_results: list[ScanResult] = []

        for tool in self.scanner_tools():
            scanner = SCANNER_BY_TOOL[tool]
            scan_results.append(
                scanner.run(
                    context.repository_path,
                    context.output_dir,
                    context.command_runner,
                    context.timeout_seconds,
                )
            )

        findings = normalize_scan_results(self.name, context.run_id, scan_results)
        ended_at = datetime.now(UTC)
        del started_at, ended_at
        return scan_results, findings


class CodeQualityAgent(DiagnosticAgent):
    name = DiagnosticAgentName.CODE_QUALITY

    def scanner_tools(self) -> tuple[ScannerTool, ...]:
        return (ScannerTool.RUFF,)


class SemgrepAgent(DiagnosticAgent):
    name = DiagnosticAgentName.SEMGREP

    def scanner_tools(self) -> tuple[ScannerTool, ...]:
        return (ScannerTool.SEMGREP,)


class SecurityAgent(DiagnosticAgent):
    name = DiagnosticAgentName.SECURITY

    def scanner_tools(self) -> tuple[ScannerTool, ...]:
        return (ScannerTool.BANDIT,)


class DependencyAgent(DiagnosticAgent):
    name = DiagnosticAgentName.DEPENDENCY

    def scanner_tools(self) -> tuple[ScannerTool, ...]:
        return (ScannerTool.OSV_SCANNER,)


class SecretCheckAgent(DiagnosticAgent):
    name = DiagnosticAgentName.SECRET_CHECK

    def scanner_tools(self) -> tuple[ScannerTool, ...]:
        return (ScannerTool.GITLEAKS,)


class TestAgent(DiagnosticAgent):
    name = DiagnosticAgentName.TEST

    def scanner_tools(self) -> tuple[ScannerTool, ...]:
        return (ScannerTool.PYTEST,)


class CoverageAgent(DiagnosticAgent):
    name = DiagnosticAgentName.COVERAGE

    def scanner_tools(self) -> tuple[ScannerTool, ...]:
        return (ScannerTool.COVERAGE,)


DEFAULT_DIAGNOSTIC_AGENTS: tuple[DiagnosticAgent, ...] = (
    CodeQualityAgent(),
    SemgrepAgent(),
    SecurityAgent(),
    DependencyAgent(),
    SecretCheckAgent(),
    TestAgent(),
    CoverageAgent(),
)

AGENT_BY_NAME: dict[DiagnosticAgentName, DiagnosticAgent] = {
    agent.name: agent for agent in DEFAULT_DIAGNOSTIC_AGENTS
}


def get_diagnostic_agents(
    selected_agents: list[DiagnosticAgentName] | None = None,
) -> list[DiagnosticAgent]:
    if selected_agents is None:
        return list(DEFAULT_DIAGNOSTIC_AGENTS)
    return [AGENT_BY_NAME[name] for name in selected_agents]
