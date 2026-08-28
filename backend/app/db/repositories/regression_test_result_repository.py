from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.regression_test_result import RegressionTestResult


class RegressionTestResultNotFoundError(Exception):
    def __init__(self, regression_test_id: str) -> None:
        self.regression_test_id = regression_test_id
        super().__init__(f"Regression test result not found: {regression_test_id}")


class RegressionTestResultRepository(BaseRepository):
    """Repository for persisted regression test results."""

    collection_name = collections.REGRESSION_TEST_RESULTS

    def add(self, result: RegressionTestResult) -> RegressionTestResult:
        document = result.model_dump(mode="json")
        document["_id"] = ObjectId(result.regression_test_id)
        document["run_id"] = ObjectId(result.run_id)
        document["patch_plan_id"] = ObjectId(result.patch_plan_id)
        document["fix_attempt_id"] = ObjectId(result.fix_attempt_id)
        document["verification_result_id"] = ObjectId(result.verification_result_id)
        self.collection.insert_one(document)
        return result

    def list_by_run(self, run_id: str) -> list[RegressionTestResult]:
        documents = self.collection.find({"run_id": ObjectId(run_id)}).sort("created_at", 1)
        return [RegressionTestResult.from_document(document) for document in documents]

    def get_by_id_for_run(
        self,
        regression_test_id: str,
        run_id: str,
    ) -> RegressionTestResult | None:
        document = self.collection.find_one(
            {"_id": ObjectId(regression_test_id), "run_id": ObjectId(run_id)},
        )
        if document is None:
            return None
        return RegressionTestResult.from_document(document)
