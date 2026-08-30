"""ADK FunctionTools — LLM agents call typed tools, tools call backend services."""

from __future__ import annotations

from google.adk.tools import FunctionTool

from app.google_adk.container import get_service_container
from app.google_adk.context import get_run_context
from app.services.code_fix_service import RiskDecisionsRequiredError
from app.services.fix_planner_service import IssueGroupsRequiredError
from app.services.peer_review_service import RegressionTestsRequiredError


def create_fix_plans() -> dict[str, object]:
    """Create structured patch plans from correlated issue groups for the current run."""
    context = get_run_context()
    services = get_service_container()
    try:
        result = services.fix_planner_service.plan_run(context.user_id, context.run_id)
    except IssueGroupsRequiredError as exc:
        return {"status": "skipped", "reason": exc.message, "plans_created": 0, "plan_ids": []}
    return {
        "status": "ok",
        "plans_created": result.patch_plan_count,
        "plan_ids": [plan.patch_plan_id for plan in result.patch_plans],
    }


def apply_autonomous_fixes() -> dict[str, object]:
    """Apply approved autonomous code fixes for eligible patch plans on the current run."""
    context = get_run_context()
    services = get_service_container()
    try:
        result = services.code_fix_service.fix_run(context.user_id, context.run_id)
    except RiskDecisionsRequiredError as exc:
        return {"status": "skipped", "reason": exc.message, "attempts": 0, "attempt_ids": []}
    return {
        "status": result.run_status,
        "attempts": result.attempt_count,
        "attempt_ids": [attempt.fix_attempt_id for attempt in result.fix_attempts],
    }


def run_multi_agent_peer_review() -> dict[str, object]:
    """Run security, testing, and architecture peer reviewers plus synthesizer."""
    context = get_run_context()
    services = get_service_container()
    try:
        result = services.peer_review_service.review_run(context.user_id, context.run_id)
    except RegressionTestsRequiredError as exc:
        return {
            "status": "skipped",
            "reason": exc.message,
            "review_count": 0,
            "verdict": None,
        }
    verdict = result.peer_reviews[0].verdict.value if result.peer_reviews else None
    return {
        "status": result.run_status,
        "review_count": result.result_count,
        "verdict": verdict,
    }


def create_fix_plans_tool() -> FunctionTool:
    return FunctionTool(create_fix_plans)


def apply_autonomous_fixes_tool() -> FunctionTool:
    return FunctionTool(apply_autonomous_fixes)


def run_multi_agent_peer_review_tool() -> FunctionTool:
    return FunctionTool(run_multi_agent_peer_review)
