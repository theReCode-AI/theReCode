import difflib
import json
from pathlib import Path

from app.adk.fixing.applicator import FixApplicationResult, FixApplicator
from app.adk.fixing.backup import PatchBackupManager, detect_changed_files, snapshot_tree_hashes
from app.adk.fixing.scope import ScopeValidator
from app.adk.fixing.working_copy import WorkingCopyManager
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.patch_plan import PatchPlan
from app.models.risk_decision import RiskDecision
from app.workspace.models import RunWorkspace


class FixExecutionResult:
    def __init__(
        self,
        *,
        status: FixAttemptStatus,
        planned_files: list[str],
        changed_files: list[str],
        unexpected_files: list[str],
        scope_violation: bool,
        backup_path: str | None,
        diff_artifact_path: str | None,
        error_message: str | None,
        application: FixApplicationResult | None = None,
    ) -> None:
        self.status = status
        self.planned_files = planned_files
        self.changed_files = changed_files
        self.unexpected_files = unexpected_files
        self.scope_violation = scope_violation
        self.backup_path = backup_path
        self.diff_artifact_path = diff_artifact_path
        self.error_message = error_message
        self.application = application


class CodeFixAgent:
    """Apply autonomous code fixes for eligible patch plans."""

    def __init__(
        self,
        working_copy_manager: WorkingCopyManager | None = None,
        backup_manager: PatchBackupManager | None = None,
        scope_validator: ScopeValidator | None = None,
    ) -> None:
        self._working_copy_manager = working_copy_manager or WorkingCopyManager()
        self._backup_manager = backup_manager or PatchBackupManager()
        self._scope_validator = scope_validator or ScopeValidator()

    def run(
        self,
        workspace: RunWorkspace,
        patch_plan: PatchPlan,
        risk_decision: RiskDecision,
        applicator: FixApplicator,
    ) -> FixExecutionResult:
        if not risk_decision.autonomous_fix_allowed:
            return FixExecutionResult(
                status=FixAttemptStatus.SKIPPED,
                planned_files=patch_plan.affected_files,
                changed_files=[],
                unexpected_files=[],
                scope_violation=False,
                backup_path=None,
                diff_artifact_path=None,
                error_message="Patch plan is not approved for autonomous fixing",
            )

        working_root = self._working_copy_manager.prepare(workspace)
        backup_root = workspace.patches / patch_plan.patch_plan_id / "pre-patch"
        plan_artifacts = workspace.patches / patch_plan.patch_plan_id
        plan_artifacts.mkdir(parents=True, exist_ok=True)

        before_hashes = snapshot_tree_hashes(working_root)
        self._backup_manager.backup_working_tree(working_root, backup_root)

        application = applicator.apply(patch_plan, str(working_root))
        if application.skipped:
            return FixExecutionResult(
                status=FixAttemptStatus.SKIPPED,
                planned_files=patch_plan.affected_files,
                changed_files=[],
                unexpected_files=[],
                scope_violation=False,
                backup_path=str(backup_root),
                diff_artifact_path=None,
                error_message=application.message,
                application=application,
            )

        if not application.applied:
            self._backup_manager.restore_working_tree(working_root, backup_root)
            return FixExecutionResult(
                status=FixAttemptStatus.FAILED,
                planned_files=patch_plan.affected_files,
                changed_files=[],
                unexpected_files=[],
                scope_violation=False,
                backup_path=str(backup_root),
                diff_artifact_path=None,
                error_message=application.message,
                application=application,
            )

        after_hashes = snapshot_tree_hashes(working_root)
        changed_files = detect_changed_files(before_hashes, after_hashes)
        scope_result = self._scope_validator.validate(patch_plan.affected_files, changed_files)

        if not scope_result.valid:
            self._backup_manager.restore_working_tree(working_root, backup_root)
            return FixExecutionResult(
                status=FixAttemptStatus.ROLLED_BACK,
                planned_files=scope_result.planned_files,
                changed_files=scope_result.changed_files,
                unexpected_files=scope_result.unexpected_files,
                scope_violation=True,
                backup_path=str(backup_root),
                diff_artifact_path=None,
                error_message=(
                    "Unexpected scope expansion detected: "
                    f"{', '.join(scope_result.unexpected_files)}"
                ),
                application=application,
            )

        diff_path = _write_diff_artifact(backup_root, working_root, changed_files, plan_artifacts)
        return FixExecutionResult(
            status=FixAttemptStatus.APPLIED,
            planned_files=scope_result.planned_files,
            changed_files=scope_result.changed_files,
            unexpected_files=[],
            scope_violation=False,
            backup_path=str(backup_root),
            diff_artifact_path=str(diff_path) if diff_path else None,
            error_message=None,
            application=application,
        )


def _write_diff_artifact(
    backup_root: Path,
    working_root: Path,
    changed_files: list[str],
    artifact_dir: Path,
) -> Path | None:
    if not changed_files:
        return None

    diff_lines: list[str] = []
    for relative_path in changed_files:
        before_path = backup_root / relative_path
        after_path = working_root / relative_path
        before_lines = (
            before_path.read_text(encoding="utf-8").splitlines(keepends=True)
            if before_path.is_file()
            else []
        )
        after_lines = (
            after_path.read_text(encoding="utf-8").splitlines(keepends=True)
            if after_path.is_file()
            else []
        )
        diff_lines.extend(
            difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
            ),
        )

    diff_path = artifact_dir / "changes.diff"
    diff_path.write_text("".join(diff_lines), encoding="utf-8")

    manifest_path = artifact_dir / "changes.json"
    manifest_path.write_text(
        json.dumps({"changed_files": changed_files}, indent=2),
        encoding="utf-8",
    )
    return diff_path
