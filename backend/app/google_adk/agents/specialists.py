"""Google ADK LlmAgent specialists backed by Gemini."""

from __future__ import annotations

from google.adk import Agent

from app.google_adk.tools.pipeline_tools import (
    apply_autonomous_fixes_tool,
    create_fix_plans_tool,
    run_multi_agent_peer_review_tool,
)

FIX_PLANNER_INSTRUCTION = """You are the Fix Planner Agent for theReCode.

Your job is to convert correlated diagnostic issue groups into structured patch plans.
Always call the create_fix_plans tool exactly once, then summarize how many plans were created.
Never modify code directly — planning is tool-driven only.
Return concise structured output."""

CODE_FIX_INSTRUCTION = """You are the Code Fix Agent for theReCode.

Apply the smallest practical autonomous fixes for eligible patch plans on this run.
Always call apply_autonomous_fixes exactly once, then summarize attempts and status.
Never commit, push, or access credentials — fixes are applied via the tool only."""

PEER_REVIEW_INSTRUCTION = """You are the Peer Review Coordinator for theReCode.

Coordinate independent security, testing, and architecture review of applied fixes.
Always call run_multi_agent_peer_review exactly once, then summarize the verdict.
Reviewers must not modify code — use the tool only."""


def build_fix_planner_agent(model: str) -> Agent:
    return Agent(
        name="fix_planner_agent",
        model=model,
        description="Creates structured patch plans from correlated findings.",
        instruction=FIX_PLANNER_INSTRUCTION,
        tools=[create_fix_plans_tool()],
    )


def build_code_fix_agent(model: str) -> Agent:
    return Agent(
        name="code_fix_agent",
        model=model,
        description="Applies autonomous code fixes through typed backend tools.",
        instruction=CODE_FIX_INSTRUCTION,
        tools=[apply_autonomous_fixes_tool()],
    )


def build_peer_review_agent(model: str) -> Agent:
    return Agent(
        name="peer_review_agent",
        model=model,
        description="Coordinates multi-agent peer review of remediated changes.",
        instruction=PEER_REVIEW_INSTRUCTION,
        tools=[run_multi_agent_peer_review_tool()],
    )
