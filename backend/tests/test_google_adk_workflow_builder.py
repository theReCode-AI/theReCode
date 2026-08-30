"""Tests for Google ADK workflow graph construction."""

from google.adk import Workflow

from app.google_adk.workflow_builder import build_therecode_workflow


def test_build_therecode_workflow_compiles_graph() -> None:
    workflow = build_therecode_workflow(model="gemini-2.5-flash")

    assert isinstance(workflow, Workflow)
    assert workflow.name == "therecode_autonomous_run"
    assert workflow.graph is not None
    assert len(workflow.graph.edges) > 0

    node_names = {node.name for node in workflow.graph.nodes}
    assert "initialize_run" in node_names
    assert "clone_repository" in node_names
    assert "finalize_run" in node_names
    assert "fix_planner_agent" in node_names
    assert "code_fix_agent" in node_names
    assert "peer_review_agent" in node_names
