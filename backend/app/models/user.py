from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class User(BaseModel):
    """User domain model stored in MongoDB."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    email: EmailStr
    full_name: str
    hashed_password: str
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_document(cls, document: dict) -> "User":
        document = document.copy()
        document["_id"] = str(document["_id"])
        return cls.model_validate(document)

    def to_document(self) -> dict:
        return {
            "email": self.email,
            "full_name": self.full_name,
            "hashed_password": self.hashed_password,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
