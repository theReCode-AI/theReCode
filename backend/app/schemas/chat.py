from datetime import datetime

from pydantic import BaseModel, Field


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class ChatMessageResponse(BaseModel):
    id: str
    run_id: str
    project_id: str
    role: str
    content: str
    created_at: datetime


class ChatSendResponse(BaseModel):
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
