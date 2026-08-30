from datetime import UTC, datetime

from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.agent_state import OrchestrationStatus, RunAgentState


class AgentStateRepository(BaseRepository):
    """Repository for orchestration state persistence."""

    collection_name = collections.AGENT_STATES

    def get_by_run(self, run_id: str) -> RunAgentState | None:
        document = self.collection.find_one({"run_id": ObjectId(run_id)})
        if document is None:
            return None
        return RunAgentState.from_document(document)

    def upsert(self, state: RunAgentState) -> RunAgentState:
        document = state.model_dump(mode="json", by_alias=True)
        document["_id"] = ObjectId(state.id)
        document["run_id"] = ObjectId(state.run_id)
        self.collection.replace_one({"run_id": ObjectId(state.run_id)}, document, upsert=True)
        return state

    def initialize(self, run_id: str) -> RunAgentState:
        now = datetime.now(UTC)
        state = RunAgentState(
            _id=str(ObjectId()),
            run_id=run_id,
            status=OrchestrationStatus.PENDING,
            progress=0,
            updated_at=now,
            created_at=now,
        )
        return self.upsert(state)

    def update_fields(self, run_id: str, **fields: object) -> RunAgentState | None:
        existing = self.get_by_run(run_id)
        if existing is None:
            return None

        updated = existing.model_copy(
            update={**fields, "updated_at": datetime.now(UTC)},
        )
        return self.upsert(updated)
