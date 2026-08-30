import pytest
from bson import ObjectId

from app.models.agent_event import AgentEventType
from app.models.run import RunStatus
from app.services.run_progress_stream_service import RunProgressStreamService
from tests.test_agent_orchestration_repository import (
    InMemoryAgentEventRepository,
    InMemoryAgentStateRepository,
)
from tests.test_run_service import InMemoryRunRepository


@pytest.mark.asyncio
async def test_stream_run_progress_emits_snapshot_and_new_events() -> None:
    run_repository = InMemoryRunRepository()
    event_repository = InMemoryAgentEventRepository()
    state_repository = InMemoryAgentStateRepository()

    run_id = str(ObjectId())
    user_id = str(ObjectId())
    project_id = str(ObjectId())
    run = run_repository.create(
        run_id=run_id,
        project_id=project_id,
        user_id=user_id,
        repository_id=None,
        workspace_path="/tmp/run-1",
        status=RunStatus.FIXING,
    )
    state_repository.initialize(run.id)
    event_repository.create_event(
        run.id,
        AgentEventType.CLONE_COMPLETED,
        "cloning",
        message="Repository cloned",
    )

    service = RunProgressStreamService(
        run_repository,
        event_repository,
        state_repository,
        poll_interval_seconds=0.01,
        heartbeat_every_polls=100,
        terminal_grace_polls=1,
    )

    stream = service.stream_run_progress(user_id, run.id)
    first_chunk = await anext(stream)
    assert "event: snapshot" in first_chunk
    assert "Repository cloned" in first_chunk

    event_repository.create_event(
        run.id,
        AgentEventType.PATCH_APPLIED,
        "code_fixing",
        message="Patch applied",
    )

    second_chunk = await anext(stream)
    assert "event: agent_event" in second_chunk
    assert "Patch applied" in second_chunk


@pytest.mark.asyncio
async def test_stream_run_progress_completes_for_terminal_run() -> None:
    run_repository = InMemoryRunRepository()
    event_repository = InMemoryAgentEventRepository()
    state_repository = InMemoryAgentStateRepository()

    run_id = str(ObjectId())
    user_id = str(ObjectId())
    project_id = str(ObjectId())
    run = run_repository.create(
        run_id=run_id,
        project_id=project_id,
        user_id=user_id,
        repository_id=None,
        workspace_path="/tmp/run-2",
        status=RunStatus.COMPLETED,
    )

    service = RunProgressStreamService(
        run_repository,
        event_repository,
        state_repository,
        poll_interval_seconds=0.01,
        heartbeat_every_polls=100,
        terminal_grace_polls=1,
    )

    stream = service.stream_run_progress(user_id, run.id)
    await anext(stream)
    complete_chunk = await anext(stream)
    assert "event: complete" in complete_chunk
