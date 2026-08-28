"""Per-run execution context for ADK workflow nodes and tools."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from app.models.finding_enums import DiagnosticAgentName


@dataclass(frozen=True)
class RunExecutionContext:
    user_id: str
    run_id: str
    branch: str | None = None
    skip_clone: bool = False
    agents: tuple[DiagnosticAgentName, ...] | None = None


_run_context: ContextVar[RunExecutionContext | None] = ContextVar(
    "codethera_run_context",
    default=None,
)


def set_run_context(context: RunExecutionContext) -> None:
    _run_context.set(context)


def get_run_context() -> RunExecutionContext:
    context = _run_context.get()
    if context is None:
        raise RuntimeError("Run execution context is not set for this ADK workflow run.")
    return context


def clear_run_context() -> None:
    _run_context.set(None)
