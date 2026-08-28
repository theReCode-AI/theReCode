from app.adk.memory.extractor import MemoryExtractionContext, MemoryExtractor
from app.models.memory_entry import MemoryEntry


class MemoryAgent:
    """ADK specialist agent that extracts durable memories from a run."""

    def __init__(self, extractor: MemoryExtractor | None = None) -> None:
        self._extractor = extractor or MemoryExtractor()

    def capture(self, context: MemoryExtractionContext) -> list[MemoryEntry]:
        return self._extractor.extract(context)
