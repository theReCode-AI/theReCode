from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.git.normalize import normalize_repository_full_name
from app.models.repository import GitProvider


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class RepositoryCreate(BaseModel):
    provider: GitProvider
    full_name: str = Field(min_length=3, max_length=300)
    default_branch: str = Field(default="main", min_length=1, max_length=200)
    clone_url: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def normalize_repository_reference(self) -> Self:
        self.full_name = normalize_repository_full_name(self.provider, self.full_name)
        return self


class RepositoryUpdate(BaseModel):
    default_branch: str | None = Field(default=None, min_length=1, max_length=200)
    clone_url: str | None = Field(default=None, max_length=500)


class RepositoryResponse(BaseModel):
    id: str
    project_id: str
    provider: GitProvider
    full_name: str
    default_branch: str
    clone_url: str | None
    created_at: datetime
    updated_at: datetime
