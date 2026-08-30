from datetime import datetime

from pydantic import BaseModel, Field

from app.models.run import RunStatus
from app.workspace.models import RunWorkspace


class RunCreate(BaseModel):
    project_id: str = Field(min_length=1)
    repository_id: str | None = Field(default=None, min_length=1)


class RunResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    repository_id: str | None
    status: RunStatus
    workspace_path: str
    created_at: datetime
    updated_at: datetime


class RunWorkspaceResponse(BaseModel):
    run_id: str
    root: str
    repository: str
    baseline: str
    working: str
    artifacts: str
    patches: str
    logs: str
    reports: str

    @classmethod
    def from_workspace(cls, workspace: RunWorkspace) -> "RunWorkspaceResponse":
        data = workspace.to_dict()
        return cls(**data)
