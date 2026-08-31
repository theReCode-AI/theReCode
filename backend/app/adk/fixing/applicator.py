"""Deterministic and LLM-backed patch applicators."""

from dataclasses import dataclass
from pathlib import Path

from app.adk.fixing.llm_rewriter import CodeRewriteError, CodeRewriter
from app.models.patch_plan import PatchPlan
from app.models.patch_plan_enums import ChangeType
from app.scanners.runner import CommandRunner, is_tool_available


@dataclass(frozen=True)
class FixApplicationResult:
    applied: bool
    skipped: bool
    message: str
    tool: str | None = None


AUTOMATED_CHANGE_TYPES = frozenset(
    {
        ChangeType.LINT_FIX.value,
        ChangeType.FORMAT_FIX.value,
    },
)


class FixApplicator:
    """Apply automated fixes for supported patch-plan change types."""

    def __init__(
        self,
        command_runner: CommandRunner,
        timeout_seconds: int = 120,
        code_rewriter: CodeRewriter | None = None,
    ) -> None:
        self._command_runner = command_runner
        self._timeout_seconds = timeout_seconds
        self._code_rewriter = code_rewriter

    def can_apply(self, patch_plan: PatchPlan) -> bool:
        change_types = {
            modification.change_type for modification in patch_plan.expected_modifications
        }
        return bool(change_types) and change_types.issubset(AUTOMATED_CHANGE_TYPES)

    def apply(
        self,
        patch_plan: PatchPlan,
        working_root: str,
        *,
        approval_gated: bool = False,
        allow_semantic_fix: bool = False,
    ) -> FixApplicationResult:
        if self.can_apply(patch_plan):
            return self._apply_ruff_to_files(patch_plan, working_root)

        if allow_semantic_fix or approval_gated:
            semantic = self._apply_semantic_rewrite(patch_plan, working_root)
            if semantic is not None:
                return semantic

        if approval_gated:
            return self._apply_ruff_to_files(
                patch_plan,
                working_root,
                fallback_message="Applied best-effort ruff fixes after human approval",
            )

        return FixApplicationResult(
            applied=False,
            skipped=True,
            message=(
                "Patch plan requires semantic remediation. "
                "Approve the risk gate or retry fixes so the LLM applicator can rewrite files."
            ),
        )

    def _apply_semantic_rewrite(
        self,
        patch_plan: PatchPlan,
        working_root: str,
    ) -> FixApplicationResult | None:
        if self._code_rewriter is None:
            return None

        try:
            changed = self._code_rewriter.rewrite_files(patch_plan, Path(working_root))
        except CodeRewriteError as exc:
            return FixApplicationResult(
                applied=False,
                skipped=False,
                message=str(exc),
                tool="gemini",
            )

        return FixApplicationResult(
            applied=True,
            skipped=False,
            message=f"Applied semantic remediation to {len(changed)} file(s)",
            tool="gemini",
        )

    def _apply_ruff_to_files(
        self,
        patch_plan: PatchPlan,
        working_root: str,
        *,
        fallback_message: str = "Applied automated lint/format fixes",
    ) -> FixApplicationResult:
        if not is_tool_available("ruff"):
            return FixApplicationResult(
                applied=False,
                skipped=False,
                message="Ruff is not available to apply lint/format fixes",
            )

        files = [
            file_path
            for file_path in patch_plan.affected_files
            if file_path and file_path != "repository"
        ]
        if not files:
            return FixApplicationResult(
                applied=False,
                skipped=True,
                message="Patch plan has no file-scoped modifications to apply",
            )

        for file_path in files:
            check_result = self._command_runner.run(
                ["ruff", "check", "--fix", file_path],
                cwd=working_root,
                timeout_seconds=self._timeout_seconds,
            )
            if check_result.exit_code not in {0, 1}:
                return FixApplicationResult(
                    applied=False,
                    skipped=False,
                    message=check_result.stderr or f"Ruff failed on {file_path}",
                    tool="ruff",
                )

            format_result = self._command_runner.run(
                ["ruff", "format", file_path],
                cwd=working_root,
                timeout_seconds=self._timeout_seconds,
            )
            if format_result.exit_code != 0:
                return FixApplicationResult(
                    applied=False,
                    skipped=False,
                    message=format_result.stderr or f"Ruff format failed on {file_path}",
                    tool="ruff",
                )

        return FixApplicationResult(
            applied=True,
            skipped=False,
            message=fallback_message,
            tool="ruff",
        )
