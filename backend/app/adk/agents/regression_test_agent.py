from pathlib import Path

from app.adk.regression.engine import RegressionExecutionResult, RegressionTestEngine
from app.models.patch_plan import PatchPlan


class RegressionTestAgent:
    """ADK specialist agent that generates and runs regression tests."""

    def __init__(self, engine: RegressionTestEngine | None = None) -> None:
        self._engine = engine

    def run(
        self,
        working_root: Path,
        patch_plan: PatchPlan,
        output_dir: Path,
        engine: RegressionTestEngine,
    ) -> RegressionExecutionResult:
        runner = self._engine or engine
        return runner.run(working_root, patch_plan, output_dir)
