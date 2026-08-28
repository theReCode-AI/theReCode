from enum import StrEnum


class AutonomyDecision(StrEnum):
    """Whether a patch plan may proceed without human approval."""

    AUTONOMOUS = "autonomous"
    REQUIRES_APPROVAL = "requires_approval"
    BLOCKED = "blocked"
