from datetime import UTC, datetime

from bson import ObjectId

from app.adk.memory.retriever import MemoryRetriever, build_planning_snippets
from app.models.finding_enums import DiagnosticAgentName, FindingSeverity
from app.models.issue_group import IssueGroup
from app.models.issue_group_enums import IssueGroupStatus
from app.models.memory_entry import MemoryEntry
from app.models.memory_enums import MemoryType


def _memory(
    memory_type: MemoryType,
    *,
    tags: list[str] | None = None,
    content: str = "content",
) -> MemoryEntry:
    return MemoryEntry(
        memory_id=str(ObjectId()),
        project_id=str(ObjectId()),
        run_id=str(ObjectId()),
        memory_type=memory_type,
        title=f"{memory_type.value} memory",
        content=content,
        tags=tags or [],
        metadata={},
        source_key=f"{memory_type.value}:1",
        created_at=datetime.now(UTC),
    )


def test_retriever_always_includes_project_and_decision_memories() -> None:
    project_memory = _memory(MemoryType.PROJECT)
    decision_memory = _memory(MemoryType.DECISION)
    failure_memory = _memory(
        MemoryType.FAILURE,
        tags=["security"],
        content="verification failed for auth module",
    )
    unrelated_failure = _memory(
        MemoryType.FAILURE,
        tags=["database"],
        content="database migration failed",
    )
    issue_group = IssueGroup(
        issue_group_id=str(ObjectId()),
        run_id=str(ObjectId()),
        title="Auth issue",
        summary="1 related finding",
        root_cause="Unsafe eval usage",
        categories=["security"],
        agents=[DiagnosticAgentName.SECURITY],
        tools=["semgrep"],
        severity=FindingSeverity.HIGH,
        priority_score=80.0,
        priority_rank=1,
        affected_files=["src/auth.py"],
        finding_ids=[],
        status=IssueGroupStatus.OPEN,
        created_at=datetime.now(UTC),
    )

    selected = MemoryRetriever().retrieve(
        [project_memory, decision_memory, failure_memory, unrelated_failure],
        [issue_group],
    )

    assert project_memory in selected
    assert decision_memory in selected
    assert failure_memory in selected
    assert unrelated_failure not in selected


def test_build_planning_snippets_formats_title_and_content() -> None:
    memory = _memory(MemoryType.PROJECT, content="Architecture=fastapi")

    snippets = build_planning_snippets([memory])

    assert snippets == ["project memory: Architecture=fastapi"]
