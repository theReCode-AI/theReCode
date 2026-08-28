"""Google ADK workflow control-flow exceptions."""

from __future__ import annotations

from app.adk.workflows.stages import OrchestrationStage


class WorkflowPausedForApprovalError(Exception):
    """Raised when the pipeline must stop until a human approves a risk gate."""

    def __init__(
        self,
        message: str = "Human approval is required before continuing the pipeline",
        stage: OrchestrationStage = OrchestrationStage.HUMAN_APPROVAL,
    ) -> None:
        self.message = message
        self.stage = stage
        super().__init__(message)
