from datetime import UTC, datetime

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.user import User


class UserRepository(BaseRepository):
    """Repository for user persistence."""

    collection_name = collections.USERS

    def get_by_email(self, email: str) -> User | None:
        document = self.collection.find_one({"email": email.lower()})
        if document is None:
            return None
        return User.from_document(document)

    def get_by_id(self, user_id: str) -> User | None:
        if not ObjectId.is_valid(user_id):
            return None

        document = self.collection.find_one({"_id": ObjectId(user_id)})
        if document is None:
            return None
        return User.from_document(document)

    def create(self, email: str, full_name: str, hashed_password: str) -> User:
        now = datetime.now(UTC)
        document = {
            "email": email.lower(),
            "full_name": full_name,
            "hashed_password": hashed_password,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        try:
            result = self.collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise UserAlreadyExistsError(email) from exc

        document["_id"] = result.inserted_id
        return User.from_document(document)


class UserAlreadyExistsError(Exception):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"User with email {email} already exists")
