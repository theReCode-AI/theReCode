from datetime import UTC, datetime
from pathlib import Path

import pytest
from bson import ObjectId

from app.adk.fixing.applicator import FixApplicator
from app.adk.fixing.backup import PatchBackupManager, detect_changed_files, snapshot_tree_hashes
from app.adk.fixing.scope import ScopeValidator
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
from app.scanners.runner import CallableCommandRunner, ProcessResult


def _patch_plan(
    change_type: str = ChangeType.LINT_FIX.value,
    files: list[str] | None = None,
) -> PatchPlan:
    now = datetime.now(UTC)
    affected = files or ["src/utils.py"]
    return PatchPlan(
        patch_plan_id=str(ObjectId()),
        run_id="run-1",
        issue_group_id=str(ObjectId()),
        title="Lint issue",
        root_cause="Unused import",
        affected_files=affected,
        expected_modifications=[
            ExpectedModification(
                file=affected[0],
                description="Remove unused import",
                change_type=change_type,
            ),
        ],
        expected_tests=["uv run ruff check src/utils.py"],
        estimated_risk=RiskLevel.LOW,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Safe lint fix",
        rollback_strategy="Revert file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )


def test_scope_validator_rejects_unexpected_files() -> None:
    result = ScopeValidator().validate(
        planned_files=["src/a.py"],
        changed_files=["src/a.py", "src/b.py"],
    )

    assert result.valid is False
    assert result.unexpected_files == ["src/b.py"]


def test_backup_and_restore_working_tree(tmp_path: Path) -> None:
    working = tmp_path / "working"
    backup = tmp_path / "backup"
    working.mkdir()
    (working / "src").mkdir()
    (working / "src" / "main.py").write_text("original\n", encoding="utf-8")

    manager = PatchBackupManager()
    manager.backup_working_tree(working, backup)
    (working / "src" / "main.py").write_text("modified\n", encoding="utf-8")

    manager.restore_working_tree(working, backup)

    assert (working / "src" / "main.py").read_text(encoding="utf-8") == "original\n"


def test_detect_changed_files(tmp_path: Path) -> None:
    before_root = tmp_path / "before"
    after_root = tmp_path / "after"
    before_root.mkdir()
    after_root.mkdir()
    (before_root / "a.py").write_text("one\n", encoding="utf-8")
    (after_root / "a.py").write_text("two\n", encoding="utf-8")
    (after_root / "b.py").write_text("new\n", encoding="utf-8")

    before = snapshot_tree_hashes(before_root)
    after = snapshot_tree_hashes(after_root)

    assert detect_changed_files(before, after) == ["a.py", "b.py"]


def test_applicator_skips_non_automated_change_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.adk.fixing.applicator.is_tool_available", lambda _: True)
    applicator = FixApplicator(CallableCommandRunner(lambda *_args: ProcessResult(
        command=[],
        cwd=".",
        exit_code=0,
        stdout="",
        stderr="",
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
    )))

    result = applicator.apply(
        _patch_plan(change_type=ChangeType.SECURITY_REMEDIATION.value),
        str(Path.cwd()),
    )

    assert result.skipped is True
    assert result.applied is False
    assert "semantic remediation" in result.message


def test_applicator_uses_semantic_rewriter_when_allowed(tmp_path: Path) -> None:
    target = tmp_path / "src" / "auth.py"
    target.parent.mkdir(parents=True)
    target.write_text("TOKEN = 'hardcoded'\n", encoding="utf-8")

    class StubRewriter:
        def rewrite_files(self, patch_plan, working_root: Path) -> list[str]:
            path = working_root / patch_plan.affected_files[0]
            path.write_text("TOKEN = os.environ['TOKEN']\n", encoding="utf-8")
            return [patch_plan.affected_files[0]]

    applicator = FixApplicator(
        CallableCommandRunner(lambda *_args: ProcessResult(
            command=[],
            cwd=".",
            exit_code=0,
            stdout="",
            stderr="",
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
        )),
        code_rewriter=StubRewriter(),
    )
    result = applicator.apply(
        _patch_plan(
            change_type=ChangeType.SECURITY_REMEDIATION.value,
            files=["src/auth.py"],
        ),
        str(tmp_path),
        allow_semantic_fix=True,
    )

    assert result.applied is True
    assert result.tool == "gemini"
    assert "os.environ" in target.read_text(encoding="utf-8")


def test_applicator_modifies_target_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.adk.fixing.applicator.is_tool_available", lambda _: True)
    target = tmp_path / "src" / "utils.py"
    target.parent.mkdir(parents=True)
    target.write_text("unused_var = 1\n", encoding="utf-8")

    def handler(command: list[str], cwd: str, timeout_seconds: int) -> ProcessResult:
        del timeout_seconds
        now = datetime.now(UTC)
        if command[0] == "ruff":
            file_path = Path(cwd) / command[-1]
            if file_path.is_file():
                content = file_path.read_text(encoding="utf-8")
                file_path.write_text(content.replace("unused_var", "fixed_var"), encoding="utf-8")
        return ProcessResult(
            command=command,
            cwd=cwd,
            exit_code=0,
            stdout="",
            stderr="",
            started_at=now,
            ended_at=now,
        )

    applicator = FixApplicator(CallableCommandRunner(handler))
    result = applicator.apply(_patch_plan(files=["src/utils.py"]), str(tmp_path))

    assert result.applied is True
    assert "fixed_var" in target.read_text(encoding="utf-8")
