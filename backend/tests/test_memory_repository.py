from app.db.repositories.memory_repository import MemoryRepository
from app.models.memory_entry import MemoryEntry


class InMemoryMemoryRepository(MemoryRepository):
    def __init__(self) -> None:
        self._entries: dict[str, MemoryEntry] = {}

    def add(self, entry: MemoryEntry) -> MemoryEntry:
        self._entries[entry.memory_id] = entry
        return entry

    def list_by_project(self, project_id: str) -> list[MemoryEntry]:
        return [
            entry
            for entry in self._entries.values()
            if entry.project_id == project_id
        ]

    def list_by_run(self, run_id: str) -> list[MemoryEntry]:
        return [entry for entry in self._entries.values() if entry.run_id == run_id]

    def get_by_id_for_project(self, memory_id: str, project_id: str) -> MemoryEntry | None:
        entry = self._entries.get(memory_id)
        if entry is None or entry.project_id != project_id:
            return None
        return entry

    def delete_by_run_and_source_keys(self, run_id: str, source_keys: list[str]) -> None:
        if not source_keys:
            return
        keys = set(source_keys)
        self._entries = {
            memory_id: entry
            for memory_id, entry in self._entries.items()
            if not (entry.run_id == run_id and entry.source_key in keys)
        }
