from enum import StrEnum


class GitOperationStatus(StrEnum):
    PENDING = "pending"
    BRANCH_CREATED = "branch_created"
    COMMITTED = "committed"
    PUSHED = "pushed"
    PR_CREATED = "pr_created"
    FAILED = "failed"
    SKIPPED = "skipped"
