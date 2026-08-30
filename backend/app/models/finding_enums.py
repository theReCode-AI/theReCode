from enum import StrEnum


class DiagnosticAgentName(StrEnum):
    CODE_QUALITY = "code_quality_agent"
    SEMGREP = "semgrep_agent"
    SECURITY = "security_agent"
    DEPENDENCY = "dependency_agent"
    SECRET_CHECK = "secret_check_agent"
    TEST = "test_agent"
    COVERAGE = "coverage_agent"


class FindingSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class FindingFixability(StrEnum):
    AGENT = "agent"
    MANUAL = "manual"
    UNKNOWN = "unknown"
