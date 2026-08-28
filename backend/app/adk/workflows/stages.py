from enum import StrEnum


class OrchestrationStage(StrEnum):
    INITIALIZATION = "initialization"
    CLONING = "cloning"
    PROJECT_INTELLIGENCE = "project_intelligence"
    DIAGNOSTICS = "diagnostics"
    ISSUE_CORRELATION = "issue_correlation"
    FIX_PLANNING = "fix_planning"
    RISK_ASSESSMENT = "risk_assessment"
    CODE_FIXING = "code_fixing"
    VERIFICATION = "verification"
    SELF_CORRECTION = "self_correction"
    REGRESSION_TESTING = "regression_testing"
    PEER_REVIEW = "peer_review"
    HUMAN_APPROVAL = "human_approval"
    MEMORY = "memory"
    GIT_FINALIZATION = "git_finalization"
    REPORTING = "reporting"
    FINALIZATION = "finalization"
