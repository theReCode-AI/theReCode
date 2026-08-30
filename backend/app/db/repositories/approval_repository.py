from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.approval import HumanApproval
from app.models.approval_enums import ApprovalStatus


class ApprovalNotFoundError(Exception):
    def __init__(self, approval_id: str) -> None:
        self.approval_id = approval_id
        super().__init__(f"Approval not found: {approval_id}")


class ApprovalRepository(BaseRepository):
    """Repository for persisted human approval requests."""

    collection_name = collections.APPROVALS

    def add(self, approval: HumanApproval) -> HumanApproval:
        document = approval.model_dump(mode="json")
        document["_id"] = ObjectId(approval.approval_id)
        document["run_id"] = ObjectId(approval.run_id)
        if approval.patch_plan_id is not None:
            document["patch_plan_id"] = ObjectId(approval.patch_plan_id)
        if approval.decided_by_user_id is not None:
            document["decided_by_user_id"] = ObjectId(approval.decided_by_user_id)
        self.collection.insert_one(document)
        return approval

    def update(self, approval: HumanApproval) -> HumanApproval:
        document = approval.model_dump(mode="json")
        approval_id = ObjectId(approval.approval_id)
        document.pop("approval_id", None)
        document["run_id"] = ObjectId(approval.run_id)
        if approval.patch_plan_id is not None:
            document["patch_plan_id"] = ObjectId(approval.patch_plan_id)
        if approval.decided_by_user_id is not None:
            document["decided_by_user_id"] = ObjectId(approval.decided_by_user_id)
        self.collection.replace_one({"_id": approval_id}, document)
        return approval

    def list_by_run(self, run_id: str) -> list[HumanApproval]:
        documents = self.collection.find({"run_id": ObjectId(run_id)}).sort("created_at", 1)
        return [HumanApproval.from_document(document) for document in documents]

    def get_by_id_for_run(self, approval_id: str, run_id: str) -> HumanApproval | None:
        document = self.collection.find_one(
            {"_id": ObjectId(approval_id), "run_id": ObjectId(run_id)},
        )
        if document is None:
            return None
        return HumanApproval.from_document(document)

    def list_pending_by_run(self, run_id: str) -> list[HumanApproval]:
        documents = self.collection.find(
            {"run_id": ObjectId(run_id), "status": ApprovalStatus.PENDING.value},
        ).sort("created_at", 1)
        return [HumanApproval.from_document(document) for document in documents]
