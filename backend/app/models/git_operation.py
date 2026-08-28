from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.git_operation_enums import GitOperationStatus
from app.models.repository import GitProvider


class GitOperation(BaseModel):
    """Persisted git finalization outcome for an autonomous run."""

    model_config = ConfigDict(populate_by_name=True)

    git_operation_id: str
    run_id: str
    project_id: str
    repository_id: str
    provider: GitProvider
    status: GitOperationStatus
    branch_name: str | None = None
    base_branch: str | None = None
    commit_sha: str | None = None
    push_commit_sha: str | None = None
    pull_request_url: str | None = None
    pull_request_number: int | None = Field(default=None, ge=1)
    title: str | None = None
    description: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    failure_summary: str | None = None
    artifact_path: str | None = None
    created_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "GitOperation":
        document = document.copy()
        document["git_operation_id"] = str(document.pop("_id"))
        document["run_id"] = str(document["run_id"])
        document["project_id"] = str(document["project_id"])
        document["repository_id"] = str(document["repository_id"])
        return cls.model_validate(document)
