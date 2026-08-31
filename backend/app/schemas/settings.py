from datetime import datetime

from pydantic import BaseModel, Field


class GeminiCredentialCreate(BaseModel):
    api_key: str = Field(min_length=1, max_length=500)
    key_label: str | None = Field(default=None, max_length=200)


class GeminiCredentialResponse(BaseModel):
    id: str
    configured: bool = True
    key_label: str | None
    created_at: datetime
    updated_at: datetime
