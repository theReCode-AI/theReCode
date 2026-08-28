"""Google Agent Development Kit 2.x integration for CodeThera."""

__all__ = [
    "GoogleAdkOrchestrator",
    "bootstrap_google_genai",
    "ensure_google_adk_configured",
]


def __getattr__(name: str):
    if name == "GoogleAdkOrchestrator":
        from app.google_adk.orchestrator import GoogleAdkOrchestrator

        return GoogleAdkOrchestrator
    if name == "bootstrap_google_genai":
        from app.google_adk.bootstrap import bootstrap_google_genai

        return bootstrap_google_genai
    if name == "ensure_google_adk_configured":
        from app.google_adk.bootstrap import ensure_google_adk_configured

        return ensure_google_adk_configured
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
