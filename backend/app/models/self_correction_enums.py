from enum import StrEnum


class SelfCorrectionStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    EXHAUSTED = "exhausted"
    SKIPPED = "skipped"
