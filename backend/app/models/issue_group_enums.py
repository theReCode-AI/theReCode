from enum import StrEnum


class IssueGroupStatus(StrEnum):
    OPEN = "open"
    PLANNED = "planned"
    FIXING = "fixing"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
