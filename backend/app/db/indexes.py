from dataclasses import dataclass, field

from pymongo import ASCENDING, DESCENDING

from app.db import collections


@dataclass(frozen=True)
class IndexDefinition:
    fields: list[tuple[str, int]]
    options: dict[str, object] = field(default_factory=dict)


INDEX_DEFINITIONS: dict[str, list[IndexDefinition]] = {
    collections.USERS: [
        IndexDefinition([("email", ASCENDING)], {"unique": True, "name": "users_email_unique"}),
        IndexDefinition([("created_at", DESCENDING)], {"name": "users_created_at"}),
    ],
    collections.PROJECTS: [
        IndexDefinition([("user_id", ASCENDING)], {"name": "projects_user_id"}),
        IndexDefinition(
            [("user_id", ASCENDING), ("name", ASCENDING)],
            {"unique": True, "name": "projects_user_id_name_unique"},
        ),
        IndexDefinition([("created_at", DESCENDING)], {"name": "projects_created_at"}),
    ],
    collections.REPOSITORIES: [
        IndexDefinition(
            [("project_id", ASCENDING), ("provider", ASCENDING), ("full_name", ASCENDING)],
            {"unique": True, "name": "repositories_project_provider_name_unique"},
        ),
    ],
    collections.RUNS: [
        IndexDefinition([("project_id", ASCENDING)], {"name": "runs_project_id"}),
        IndexDefinition([("status", ASCENDING)], {"name": "runs_status"}),
        IndexDefinition([("created_at", DESCENDING)], {"name": "runs_created_at"}),
    ],
    collections.AGENT_EVENTS: [
        IndexDefinition([("run_id", ASCENDING)], {"name": "agent_events_run_id"}),
        IndexDefinition(
            [("run_id", ASCENDING), ("created_at", ASCENDING)],
            {"name": "agent_events_run_id_created_at"},
        ),
    ],
    collections.AGENT_STATES: [
        IndexDefinition(
            [("run_id", ASCENDING)],
            {"unique": True, "name": "agent_states_run_id_unique"},
        ),
    ],
    collections.FINDINGS: [
        IndexDefinition([("run_id", ASCENDING)], {"name": "findings_run_id"}),
        IndexDefinition([("status", ASCENDING)], {"name": "findings_status"}),
    ],
    collections.ISSUE_GROUPS: [
        IndexDefinition([("run_id", ASCENDING)], {"name": "issue_groups_run_id"}),
    ],
    collections.FIX_PLANS: [
        IndexDefinition([("run_id", ASCENDING)], {"name": "fix_plans_run_id"}),
    ],
    collections.RISK_DECISIONS: [
        IndexDefinition([("run_id", ASCENDING)], {"name": "risk_decisions_run_id"}),
        IndexDefinition(
            [("patch_plan_id", ASCENDING)],
            {"unique": True, "name": "risk_decisions_patch_plan_id_unique"},
        ),
    ],
    collections.FIX_ATTEMPTS: [
        IndexDefinition([("run_id", ASCENDING)], {"name": "fix_attempts_run_id"}),
    ],
    collections.VERIFICATION_RESULTS: [
        IndexDefinition([("run_id", ASCENDING)], {"name": "verification_results_run_id"}),
    ],
    collections.SELF_CORRECTION_CYCLES: [
        IndexDefinition([("run_id", ASCENDING)], {"name": "self_correction_cycles_run_id"}),
    ],
    collections.REGRESSION_TEST_RESULTS: [
        IndexDefinition([("run_id", ASCENDING)], {"name": "regression_test_results_run_id"}),
    ],
    collections.REVIEWS: [
        IndexDefinition([("run_id", ASCENDING)], {"name": "reviews_run_id"}),
    ],
    collections.APPROVALS: [
        IndexDefinition([("run_id", ASCENDING)], {"name": "approvals_run_id"}),
        IndexDefinition([("status", ASCENDING)], {"name": "approvals_status"}),
    ],
    collections.MEMORIES: [
        IndexDefinition([("project_id", ASCENDING)], {"name": "memories_project_id"}),
        IndexDefinition([("memory_type", ASCENDING)], {"name": "memories_memory_type"}),
    ],
    collections.GIT_OPERATIONS: [
        IndexDefinition([("run_id", ASCENDING)], {"name": "git_operations_run_id"}),
    ],
    collections.GIT_CREDENTIALS: [
        IndexDefinition(
            [("user_id", ASCENDING), ("provider", ASCENDING)],
            {"unique": True, "name": "git_credentials_user_provider_unique"},
        ),
    ],
    collections.REPORTS: [
        IndexDefinition([("run_id", ASCENDING)], {"unique": True, "name": "reports_run_id_unique"}),
    ],
    collections.CHAT_MESSAGES: [
        IndexDefinition(
            [("run_id", ASCENDING), ("user_id", ASCENDING), ("created_at", ASCENDING)],
            {"name": "chat_messages_run_user_created_at"},
        ),
        IndexDefinition([("project_id", ASCENDING)], {"name": "chat_messages_project_id"}),
    ],
}
