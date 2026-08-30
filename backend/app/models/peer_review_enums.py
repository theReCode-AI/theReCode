from enum import StrEnum


class ReviewerRole(StrEnum):
    SECURITY = "security_reviewer"
    TESTING = "testing_reviewer"
    ARCHITECTURE = "architecture_reviewer"
    SYNTHESIZER = "peer_review_synthesizer"


class ReviewerDecision(StrEnum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"


class PeerReviewVerdict(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
