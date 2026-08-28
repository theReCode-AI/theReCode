from app.db.repositories.regression_test_result_repository import RegressionTestResultRepository
from app.models.regression_test_result import RegressionTestResult


class InMemoryRegressionTestResultRepository(RegressionTestResultRepository):
    def __init__(self) -> None:
        self._results: dict[str, list[RegressionTestResult]] = {}

    def add(self, result: RegressionTestResult) -> RegressionTestResult:
        self._results.setdefault(result.run_id, []).append(result)
        return result

    def list_by_run(self, run_id: str) -> list[RegressionTestResult]:
        return list(self._results.get(run_id, []))

    def get_by_id_for_run(
        self,
        regression_test_id: str,
        run_id: str,
    ) -> RegressionTestResult | None:
        for result in self._results.get(run_id, []):
            if result.regression_test_id == regression_test_id:
                return result
        return None
