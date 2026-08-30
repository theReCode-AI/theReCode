"""Retrieve relevant project memories for planning and remediation."""

from __future__ import annotations

from app.models.issue_group import IssueGroup
from app.models.memory_entry import MemoryEntry
from app.models.memory_enums import MemoryType


class MemoryRetriever:
    """Select memories relevant to the current planning context."""

    def retrieve(
        self,
        memories: list[MemoryEntry],
        issue_groups: list[IssueGroup],
    ) -> list[MemoryEntry]:
        if not memories:
            return []

        categories = _issue_categories(issue_groups)
        selected: list[MemoryEntry] = []
        seen_ids: set[str] = set()

        for memory in memories:
            if memory.memory_type == MemoryType.PROJECT:
                _add_memory(selected, seen_ids, memory)
                continue

            if memory.memory_type == MemoryType.DECISION:
                _add_memory(selected, seen_ids, memory)
                continue

            if _matches_categories(memory, categories):
                _add_memory(selected, seen_ids, memory)

        return selected


def build_planning_snippets(memories: list[MemoryEntry]) -> list[str]:
    return [f"{memory.title}: {memory.content}" for memory in memories]


def _issue_categories(issue_groups: list[IssueGroup]) -> set[str]:
    categories: set[str] = set()
    for issue_group in issue_groups:
        categories.update(issue_group.categories)
        categories.add(issue_group.root_cause.lower())
    return {category.lower() for category in categories if category}


def _matches_categories(memory: MemoryEntry, categories: set[str]) -> bool:
    if not categories:
        return False
    searchable = " ".join(memory.tags).lower() + " " + memory.content.lower()
    return any(category in searchable for category in categories)


def _add_memory(
    selected: list[MemoryEntry],
    seen_ids: set[str],
    memory: MemoryEntry,
) -> None:
    if memory.memory_id in seen_ids:
        return
    seen_ids.add(memory.memory_id)
    selected.append(memory)
