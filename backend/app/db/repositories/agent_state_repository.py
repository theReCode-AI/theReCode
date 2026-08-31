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
        document.pop("id", None)
        document["run_id"] = ObjectId(state.run_id)
        preserved_id = self.replace_one_preserving_id(
            filter_query={"run_id": ObjectId(state.run_id)},
            document=document,
            new_id=state.id,
        )
        return state.model_copy(update={"id": preserved_id})

    def initialize(self, run_id: str) -> RunAgentState:
        existing = self.get_by_run(run_id)
        now = datetime.now(UTC)
        if existing is not None:
            return self.upsert(
                existing.model_copy(
                    update={
                        "status": OrchestrationStatus.PENDING,
                        "progress": 0,
                        "error_message": None,
                        "approval_required": False,
                        "updated_at": now,
                    },
                ),
            )

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
