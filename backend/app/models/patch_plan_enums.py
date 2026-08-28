from enum import StrEnum


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    BLOCKED = "blocked"


class PatchPlanStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


class FixScope(StrEnum):
    SINGLE_FILE = "single_file"
    MULTI_FILE = "multi_file"
    REPOSITORY = "repository"
    DEPENDENCY = "dependency"


class ChangeType(StrEnum):
    LINT_FIX = "lint_fix"
    FORMAT_FIX = "format_fix"
    SECURITY_REMEDIATION = "security_remediation"
    SECRET_REMOVAL = "secret_removal"
    TEST_FIX = "test_fix"
    TEST_ADDITION = "test_addition"
    DEPENDENCY_UPDATE = "dependency_update"
    COVERAGE_IMPROVEMENT = "coverage_improvement"
    MANUAL_REVIEW = "manual_review"
