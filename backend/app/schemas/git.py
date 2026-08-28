from datetime import datetime

from pydantic import BaseModel, Field

from app.models.repository import GitProvider


class GitCredentialCreate(BaseModel):
    provider: GitProvider
    access_token: str = Field(min_length=1, max_length=500)
    token_label: str | None = Field(default=None, max_length=200)


class GitCredentialResponse(BaseModel):
    id: str
    provider: GitProvider
    token_label: str | None
    created_at: datetime
    updated_at: datetime


class RepositoryValidationResponse(BaseModel):
    valid: bool
    provider: GitProvider
    full_name: str
    default_branch: str
    clone_url: str
    html_url: str | None = None
    message: str | None = None


class RepositoryCloneRequest(BaseModel):
    branch: str | None = Field(default=None, min_length=1, max_length=200)
    run_id: str | None = Field(default=None, min_length=24, max_length=24)


class RepositoryCloneResponse(BaseModel):
    success: bool
    destination: str
    branch: str
    commit_sha: str | None = None
    message: str | None = None
