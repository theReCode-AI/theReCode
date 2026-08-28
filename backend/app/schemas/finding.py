from datetime import datetime

from pydantic import BaseModel, Field

from app.models.finding import Finding
from app.models.finding_enums import DiagnosticAgentName
from app.models.scan import ScanResult


class FindingResponse(Finding):
    """API response for a persisted finding."""


class AgentDiagnosticResult(BaseModel):
    agent: DiagnosticAgentName
    scan_results: list[ScanResult]
    findings: list[Finding]
    started_at: datetime
    ended_at: datetime
    duration_ms: int


class DiagnosticAgentsResponse(BaseModel):
    run_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    agents: list[AgentDiagnosticResult]
    findings: list[FindingResponse]
    finding_count: int


class RunDiagnosticAgentsRequest(BaseModel):
    agents: list[DiagnosticAgentName] | None = Field(
        default=None,
        description="Optional subset of diagnostic agents to run.",
    )
