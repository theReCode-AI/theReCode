from datetime import UTC, datetime
from pathlib import Path

import pytest
from bson import ObjectId

from app.models.fix_attempt import FixAttempt
from app.models.fix_attempt_enums import FixAttemptStatus
from app.services.code_fix_service import CodeFixService, FixAttemptDiffNotFoundError
from app.workspace.models import RunWorkspace
from tests.test_agent_orchestration_repository import InMemoryAgentEventRepository
from tests.test_fix_attempt_repository import InMemoryFixAttemptRepository
from tests.test_fix_plan_repository import InMemoryFixPlanRepository
from tests.test_risk_decision_repository import InMemoryRiskDecisionRepository
from tests.test_run_service import InMemoryRunRepository


class StubRunService:
    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root

    def get_workspace_for_run(self, user_id: str, run_id: str) -> RunWorkspace:
        return RunWorkspace(run_id=run_id, root=self._workspace_root)


def _build_service(tmp_path: Path, fix_attempt_repository: InMemoryFixAttemptRepository):
    run_repository = InMemoryRunRepository()
    return (
        run_repository,
        CodeFixService(
            run_repository=run_repository,
            run_service=StubRunService(tmp_path),
            fix_plan_repository=InMemoryFixPlanRepository(),
            risk_decision_repository=InMemoryRiskDecisionRepository(),
            fix_attempt_repository=fix_attempt_repository,
            event_repository=InMemoryAgentEventRepository(),
        ),
    )


def test_get_fix_attempt_diff_returns_content(tmp_path: Path) -> None:
    run_id = str(ObjectId())
    user_id = str(ObjectId())
    project_id = str(ObjectId())
    fix_attempt_id = str(ObjectId())

    fix_attempt_repository = InMemoryFixAttemptRepository()
    run_repository, service = _build_service(tmp_path, fix_attempt_repository)
    run_repository.create(
        run_id=run_id,
        project_id=project_id,
        user_id=user_id,
        repository_id=None,
        workspace_path=str(tmp_path),
    )

    diff_path = tmp_path / "patches" / "plan" / "changes.diff"
    diff_path.parent.mkdir(parents=True)
    diff_path.write_text("--- a/file.py\n+++ b/file.py\n", encoding="utf-8")

    fix_attempt_repository.add(
        FixAttempt(
            fix_attempt_id=fix_attempt_id,
            run_id=run_id,
            patch_plan_id=str(ObjectId()),
            attempt_number=1,
            status=FixAttemptStatus.APPLIED,
            planned_files=["file.py"],
            changed_files=["file.py"],
            diff_artifact_path=str(diff_path),
            created_at=datetime.now(UTC),
        ),
    )

    response = service.get_fix_attempt_diff(user_id, run_id, fix_attempt_id)
    assert response.content.startswith("--- a/file.py")
    assert response.changed_files == ["file.py"]


def test_get_fix_attempt_diff_raises_when_missing(tmp_path: Path) -> None:
    run_id = str(ObjectId())
    user_id = str(ObjectId())
    project_id = str(ObjectId())
    fix_attempt_id = str(ObjectId())

    fix_attempt_repository = InMemoryFixAttemptRepository()
    run_repository, service = _build_service(tmp_path, fix_attempt_repository)
    run_repository.create(
        run_id=run_id,
        project_id=project_id,
        user_id=user_id,
        repository_id=None,
        workspace_path=str(tmp_path),
    )

    fix_attempt_repository.add(
        FixAttempt(
            fix_attempt_id=fix_attempt_id,
            run_id=run_id,
            patch_plan_id=str(ObjectId()),
            attempt_number=1,
            status=FixAttemptStatus.APPLIED,
            planned_files=["file.py"],
            changed_files=["file.py"],
            diff_artifact_path=None,
            created_at=datetime.now(UTC),
        ),
    )

    with pytest.raises(FixAttemptDiffNotFoundError):
        service.get_fix_attempt_diff(user_id, run_id, fix_attempt_id)
