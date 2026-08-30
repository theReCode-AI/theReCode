from app.db.repositories.approval_repository import ApprovalRepository
from app.models.approval import HumanApproval


class InMemoryApprovalRepository(ApprovalRepository):
    def __init__(self) -> None:
        self._approvals: dict[str, list[HumanApproval]] = {}

    def add(self, approval: HumanApproval) -> HumanApproval:
        self._approvals.setdefault(approval.run_id, []).append(approval)
        return approval

    def update(self, approval: HumanApproval) -> HumanApproval:
        approvals = self._approvals.get(approval.run_id, [])
        for index, existing in enumerate(approvals):
            if existing.approval_id == approval.approval_id:
                approvals[index] = approval
                return approval
        approvals.append(approval)
        self._approvals[approval.run_id] = approvals
        return approval

    def list_by_run(self, run_id: str) -> list[HumanApproval]:
        return list(self._approvals.get(run_id, []))

    def get_by_id_for_run(self, approval_id: str, run_id: str) -> HumanApproval | None:
        for approval in self._approvals.get(run_id, []):
            if approval.approval_id == approval_id:
                return approval
        return None

    def list_pending_by_run(self, run_id: str) -> list[HumanApproval]:
        from app.models.approval_enums import ApprovalStatus

        return [
            approval
            for approval in self._approvals.get(run_id, [])
            if approval.status == ApprovalStatus.PENDING
        ]
