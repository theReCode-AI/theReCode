from datetime import datetime

from pydantic import BaseModel

from app.models.run_report import RunReport


class RunReportResponse(RunReport):
    """API response for a persisted run report."""


class RunReportMarkdownResponse(BaseModel):
    report_id: str
    run_id: str
    markdown: str


class GenerateRunReportResponse(BaseModel):
    run_id: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    report: RunReportResponse
    run_status: str
