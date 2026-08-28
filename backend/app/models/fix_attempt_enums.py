from enum import StrEnum


class FixAttemptStatus(StrEnum):
    APPLIED = "applied"
    SKIPPED = "skipped"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
