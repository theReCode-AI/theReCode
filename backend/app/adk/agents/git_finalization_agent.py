from app.adk.git_finalization.engine import (
    GitFinalizationContext,
    GitFinalizationEngine,
    GitFinalizationResult,
)


class GitFinalizationAgent:
    """ADK specialist agent that finalizes remediated code through git."""

    def __init__(self, engine: GitFinalizationEngine | None = None) -> None:
        self._engine = engine or GitFinalizationEngine()

    def finalize(
        self,
        context: GitFinalizationContext,
        provider,
        access_token: str,
    ) -> GitFinalizationResult:
        return self._engine.finalize(context, provider, access_token)
