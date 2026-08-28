from datetime import UTC, datetime

from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.agent_event import AgentEvent, AgentEventType


class AgentEventRepository(BaseRepository):
    """Repository for orchestration event persistence."""

    collection_name = collections.AGENT_EVENTS

    def append(self, event: AgentEvent) -> AgentEvent:
        document = event.model_dump(mode="json", by_alias=True)
        document["_id"] = ObjectId(event.id)
        document["run_id"] = ObjectId(event.run_id)
        self.collection.insert_one(document)
        return event

    def list_by_run(self, run_id: str) -> list[AgentEvent]:
        documents = self.collection.find({"run_id": ObjectId(run_id)}).sort("created_at", 1)
        return [AgentEvent.from_document(document) for document in documents]

    def list_by_run_after(self, run_id: str, after_created_at: datetime | None) -> list[AgentEvent]:
        query: dict[str, object] = {"run_id": ObjectId(run_id)}
        if after_created_at is not None:
            query["created_at"] = {"$gt": after_created_at}

        documents = self.collection.find(query).sort("created_at", 1)
        return [AgentEvent.from_document(document) for document in documents]

    def create_event(
        self,
        run_id: str,
        event_type: AgentEventType,
        stage: str,
        *,
        agent: str | None = None,
        tool: str | None = None,
        status: str = "ok",
        message: str | None = None,
        payload: dict | None = None,
    ) -> AgentEvent:
        now = datetime.now(UTC)
        event = AgentEvent(
            _id=str(ObjectId()),
            run_id=run_id,
            event_type=event_type,
            stage=stage,
            agent=agent,
            tool=tool,
            status=status,
            message=message,
            payload=payload or {},
            created_at=now,
        )
        return self.append(event)
