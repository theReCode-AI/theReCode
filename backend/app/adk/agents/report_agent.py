from pathlib import Path

from app.adk.reporting.engine import ReportGenerationEngine
from app.adk.reporting.markdown_builder import ReportGenerationContext


class ReportAgent:
    """ADK specialist agent that generates run reports."""

    def __init__(self, engine: ReportGenerationEngine | None = None) -> None:
        self._engine = engine or ReportGenerationEngine()

    def generate(self, context: ReportGenerationContext, output_dir: Path):
        return self._engine.generate(context, output_dir)
