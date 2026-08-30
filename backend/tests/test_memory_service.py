from datetime import UTC, datetime
from pathlib import Path

import pytest
from bson import ObjectId

from app.models.approval import HumanApproval
from app.models.approval_enums import ApprovalStatus, ApprovalTrigger, HumanDecision
from app.models.project_intelligence import (
    ApplicationArchitecture,
    PackageManager,
    ProjectIntelligence,
)
from app.models.run import RunStatus
from app.schemas.project import ProjectCreate
from app.schemas.run import RunCreate
from app.services.memory_service import PROJECT_MEMORIES_ARTIFACT_NAME, MemoryService
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.workspace import WorkspaceManager
from tests.test_agent_orchestration_repository import InMemoryAgentEventRepository
from tests.test_approval_repository import InMemoryApprovalRepository
from tests.test_fix_attempt_repository import InMemoryFixAttemptRepository
from tests.test_fix_plan_repository import InMemoryFixPlanRepository
from tests.test_memory_repository import InMemoryMemoryRepository
from tests.test_peer_review_result_repository import InMemoryPeerReviewResultRepository
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_regression_test_result_repository import InMemoryRegressionTestResultRepository
from tests.test_run_service import InMemoryRunRepository
from tests.test_self_correction_cycle_repository import InMemorySelfCorrectionCycleRepository
from tests.test_verification_result_repository import InMemoryVerificationResultRepository


@pytest.fixture
def memory_stack(tmp_path: Path):
    run_repository = InMemoryRunRepository()
    memory_repository = InMemoryMemoryRepository()
    event_repository = InMemoryAgentEventRepository()
    workspace_manager = WorkspaceManager(tmp_path)
    project_service = ProjectService(
        InMemoryProjectRepository(),
        InMemoryLinkedRepositoryRepository(),
    )
    run_service = RunService(run_repository, project_service, workspace_manager)
    service = MemoryService(
        run_repository=run_repository,
        run_service=run_service,
        project_service=project_service,
        fix_plan_repository=InMemoryFixPlanRepository(),
        approval_repository=InMemoryApprovalRepository(),
        fix_attempt_repository=InMemoryFixAttemptRepository(),
        verification_result_repository=InMemoryVerificationResultRepository(),
        regression_test_result_repository=InMemoryRegressionTestResultRepository(),
        peer_review_result_repository=InMemoryPeerReviewResultRepository(),
        self_correction_cycle_repository=InMemorySelfCorrectionCycleRepository(),
        memory_repository=memory_repository,
        event_repository=event_repository,
    )
    return (
        service,
        run_service,
        project_service,
        run_repository,
        memory_repository,
        workspace_manager,
    )


def test_capture_run_memory_persists_project_and_decision_entries(memory_stack) -> None:
    (
        service,
        run_service,
        project_service,
        run_repository,
        memory_repository,
        workspace_manager,
    ) = memory_stack
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Memory Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    run_repository.update_project_intelligence(
        run.id,
        user_id,
        ProjectIntelligence(
            language="python",
            package_manager=PackageManager.UV,
            frameworks=["fastapi"],
            architecture=ApplicationArchitecture.FASTAPI,
            entrypoints=["src/main.py"],
            source_directories=["src"],
            test_directories=["tests"],
        ),
        RunStatus.FINAL_REVIEW,
    )
    now = datetime.now(UTC)
    approval = HumanApproval(
        approval_id=str(ObjectId()),
        run_id=run.id,
        patch_plan_id=str(ObjectId()),
        trigger=ApprovalTrigger.RISK_GATE,
        status=ApprovalStatus.APPROVED,
        reason="High risk patch",
        human_decision=HumanDecision.APPROVE,
        human_feedback="Proceed with caution",
        created_at=now,
    )
    service._approval_repository.add(approval)

    response = service.capture_run_memory(user_id, run.id)
    workspace = workspace_manager.get_run_workspace(run.id)

    assert response.memory_count >= 2
    assert response.project_memory_count >= 1
    assert response.decision_memory_count >= 1
    assert len(memory_repository.list_by_project(project.id)) == response.memory_count
    assert (workspace.baseline / PROJECT_MEMORIES_ARTIFACT_NAME).is_file()


def test_list_and_get_project_memory(memory_stack) -> None:
    service, run_service, project_service, run_repository, memory_repository, _ = memory_stack
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="List Memory"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    run_repository.update_project_intelligence(
        run.id,
        user_id,
        ProjectIntelligence(
            language="python",
            package_manager=PackageManager.UV,
            frameworks=["fastapi"],
            architecture=ApplicationArchitecture.FASTAPI,
        ),
        RunStatus.FINAL_REVIEW,
    )

    captured = service.capture_run_memory(user_id, run.id)
    listed = service.list_project_memories(user_id, project.id)
    fetched = service.get_project_memory(
        user_id,
        project.id,
        captured.memories[0].memory_id,
    )

    assert len(listed) == captured.memory_count
    assert fetched.memory_id == captured.memories[0].memory_id
