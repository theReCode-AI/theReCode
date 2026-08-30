from enum import StrEnum


class VerificationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class VerificationCheckType(StrEnum):
    COMMAND = "command"
    SCANNER = "scanner"


class VerificationCheckStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
