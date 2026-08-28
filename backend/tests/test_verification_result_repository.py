from app.db.repositories.verification_result_repository import VerificationResultRepository
from app.models.verification_result import VerificationResult


class InMemoryVerificationResultRepository(VerificationResultRepository):
    def __init__(self) -> None:
        self._verification_results: dict[str, list[VerificationResult]] = {}

    def add(self, verification_result: VerificationResult) -> VerificationResult:
        self._verification_results.setdefault(verification_result.run_id, []).append(
            verification_result,
        )
        return verification_result

    def list_by_run(self, run_id: str) -> list[VerificationResult]:
        return list(self._verification_results.get(run_id, []))

    def get_by_id_for_run(
        self,
        verification_result_id: str,
        run_id: str,
    ) -> VerificationResult | None:
        for result in self._verification_results.get(run_id, []):
            if result.verification_result_id == verification_result_id:
                return result
        return None
