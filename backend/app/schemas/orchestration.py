from pydantic import BaseModel, Field

from app.models.agent_event import AgentEvent
from app.models.agent_state import RunAgentState
from app.models.finding_enums import DiagnosticAgentName
from app.schemas.run import RunResponse


class AgentEventResponse(AgentEvent):
    """API response for a persisted agent event."""


class RunAgentStateResponse(RunAgentState):
    """API response for orchestration state."""


class RunOrchestrationRequest(BaseModel):
    branch: str | None = Field(default=None, min_length=1)
    skip_clone: bool = False
    resume_after_approval: bool = False
    agents: list[DiagnosticAgentName] | None = Field(
        default=None,
        description="Optional subset of diagnostic agents to run.",
    )


class RunOrchestrationResponse(BaseModel):
    run_id: str
    state: RunAgentStateResponse
    event_count: int


class RunProgressSnapshot(BaseModel):
    run: RunResponse
    state: RunAgentStateResponse | None = None
    events: list[AgentEventResponse] = Field(default_factory=list)
