from app.db.repositories.peer_review_result_repository import PeerReviewResultRepository
from app.models.peer_review_result import PeerReviewResult


class InMemoryPeerReviewResultRepository(PeerReviewResultRepository):
    def __init__(self) -> None:
        self._results: dict[str, list[PeerReviewResult]] = {}

    def add(self, result: PeerReviewResult) -> PeerReviewResult:
        self._results.setdefault(result.run_id, []).append(result)
        return result

    def list_by_run(self, run_id: str) -> list[PeerReviewResult]:
        return list(self._results.get(run_id, []))

    def get_by_id_for_run(self, peer_review_id: str, run_id: str) -> PeerReviewResult | None:
        for result in self._results.get(run_id, []):
            if result.peer_review_id == peer_review_id:
                return result
        return None
