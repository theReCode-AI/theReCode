from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.run_report import RunReport


class ReportNotFoundError(Exception):
    def __init__(self, report_id: str) -> None:
        self.report_id = report_id
        super().__init__(f"Report not found: {report_id}")


class ReportRepository(BaseRepository):
    """Repository for persisted run reports."""

    collection_name = collections.REPORTS

    def upsert_for_run(self, report: RunReport) -> RunReport:
        document = report.model_dump(mode="json")
        document["_id"] = ObjectId(report.report_id)
        document["run_id"] = ObjectId(report.run_id)
        document["project_id"] = ObjectId(report.project_id)
        self.collection.replace_one({"run_id": ObjectId(report.run_id)}, document, upsert=True)
        return report

    def get_by_run(self, run_id: str) -> RunReport | None:
        document = self.collection.find_one({"run_id": ObjectId(run_id)})
        if document is None:
            return None
        return RunReport.from_document(document)

    def get_by_id_for_run(self, report_id: str, run_id: str) -> RunReport | None:
        document = self.collection.find_one(
            {"_id": ObjectId(report_id), "run_id": ObjectId(run_id)},
        )
        if document is None:
            return None
        return RunReport.from_document(document)
