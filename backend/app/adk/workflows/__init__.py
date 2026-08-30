"""ADK workflow modules."""

__all__ = ["RootOrchestrator"]


def __getattr__(name: str):
    if name == "RootOrchestrator":
        from app.adk.workflows.root_orchestrator import RootOrchestrator

        return RootOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
