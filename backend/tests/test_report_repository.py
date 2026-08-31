from app.db.repositories.report_repository import ReportRepository
from app.models.run_report import RunReport


class InMemoryReportRepository(ReportRepository):
    def __init__(self) -> None:
        self._reports_by_run: dict[str, RunReport] = {}

    def upsert_for_run(self, report: RunReport) -> RunReport:
        existing = self._reports_by_run.get(report.run_id)
        if existing is not None:
            report = report.model_copy(update={"report_id": existing.report_id})
        self._reports_by_run[report.run_id] = report
        return report

    def get_by_run(self, run_id: str) -> RunReport | None:
        return self._reports_by_run.get(run_id)

    def get_by_id_for_run(self, report_id: str, run_id: str) -> RunReport | None:
        report = self._reports_by_run.get(run_id)
        if report is None or report.report_id != report_id:
            return None
        return report
