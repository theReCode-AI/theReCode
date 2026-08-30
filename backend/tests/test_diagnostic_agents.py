from app.adk.agents.diagnostic_agents import (
    AGENT_BY_NAME,
    DEFAULT_DIAGNOSTIC_AGENTS,
    SecurityAgent,
    SemgrepAgent,
)
from app.models.finding_enums import DiagnosticAgentName
from app.models.scan import ScannerTool


def test_semgrep_agent_runs_semgrep_only() -> None:
    agent = SemgrepAgent()

    assert agent.name == DiagnosticAgentName.SEMGREP
    assert agent.scanner_tools() == (ScannerTool.SEMGREP,)


def test_security_agent_runs_bandit_only() -> None:
    agent = SecurityAgent()

    assert agent.name == DiagnosticAgentName.SECURITY
    assert agent.scanner_tools() == (ScannerTool.BANDIT,)


def test_default_diagnostic_agents_include_semgrep() -> None:
    agent_names = {agent.name for agent in DEFAULT_DIAGNOSTIC_AGENTS}

    assert DiagnosticAgentName.SEMGREP in agent_names
    assert AGENT_BY_NAME[DiagnosticAgentName.SEMGREP] is not None
