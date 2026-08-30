"""Build the theReCode root Google ADK 2.0 workflow graph."""

from __future__ import annotations

from google.adk import Workflow

from app.google_adk.agents.specialists import (
    build_code_fix_agent,
    build_fix_planner_agent,
    build_peer_review_agent,
)
from app.google_adk.nodes import pipeline_nodes as nodes


def build_therecode_workflow(*, model: str) -> Workflow:
    """Return the full autonomous run workflow orchestrated by Google ADK 2.0."""
    fix_planner = build_fix_planner_agent(model)
    code_fix = build_code_fix_agent(model)
    peer_review = build_peer_review_agent(model)

    return Workflow(
        name="therecode_autonomous_run",
        edges=[
            (
                "START",
                nodes.initialize_run,
                nodes.clone_repository,
                nodes.analyze_project_intelligence,
                nodes.run_diagnostics,
                nodes.correlate_findings,
                fix_planner,
                nodes.assess_risk,
                nodes.gate_risk_approval,
                code_fix,
                nodes.verify_fixes,
                nodes.self_correct,
                nodes.run_regression_tests,
                peer_review,
                nodes.prepare_human_approvals,
                nodes.capture_memory,
                nodes.finalize_git,
                nodes.generate_report,
                nodes.finalize_run,
            ),
        ],
    )


def build_post_risk_approval_workflow(*, model: str) -> Workflow:
    """Resume the run after risk-gate human approval."""
    code_fix = build_code_fix_agent(model)
    peer_review = build_peer_review_agent(model)

    return Workflow(
        name="therecode_post_risk_approval_run",
        edges=[
            (
                "START",
                code_fix,
                nodes.verify_fixes,
                nodes.self_correct,
                nodes.run_regression_tests,
                peer_review,
                nodes.prepare_human_approvals,
                nodes.capture_memory,
                nodes.finalize_git,
                nodes.generate_report,
                nodes.finalize_run,
            ),
        ],
    )
