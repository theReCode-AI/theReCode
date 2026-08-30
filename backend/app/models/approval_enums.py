from enum import StrEnum


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


class ApprovalTrigger(StrEnum):
    RISK_GATE = "risk_gate"
    PEER_REVIEW = "peer_review"
    SELF_CORRECTION_EXHAUSTED = "self_correction_exhausted"


class HumanDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
