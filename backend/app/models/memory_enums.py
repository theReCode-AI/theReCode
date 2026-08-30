from enum import StrEnum


class MemoryType(StrEnum):
    PROJECT = "project"
    DECISION = "decision"
    FAILURE = "failure"
    SUCCESS_STRATEGY = "success_strategy"
