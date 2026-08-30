from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.report_enums import ReportStatus


class RunReport(BaseModel):
    """Persisted markdown and PDF report for an autonomous run."""

    model_config = ConfigDict(populate_by_name=True)

    report_id: str
    run_id: str
    project_id: str
    status: ReportStatus
    markdown_path: str
    pdf_path: str
    final_health_score: float = Field(ge=0.0, le=100.0)
    pull_request_url: str | None = None
    branch_name: str | None = None
    commit_sha: str | None = None
    duration_ms: int = Field(ge=0, default=0)
    tool_versions: dict[str, str] = Field(default_factory=dict)
    artifact_path: str | None = None
    created_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "RunReport":
        document = document.copy()
        document["report_id"] = str(document.pop("_id"))
        document["run_id"] = str(document["run_id"])
        document["project_id"] = str(document["project_id"])
        return cls.model_validate(document)
