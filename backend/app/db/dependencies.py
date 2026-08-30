from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.db.mongodb import MongoDBManager, mongodb_manager


def get_mongodb_manager() -> MongoDBManager:
    return mongodb_manager


def get_database(
    manager: MongoDBManager = Depends(get_mongodb_manager),
) -> Generator[Database, None, None]:
    try:
        manager.ensure_connected()
    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "MongoDB is unreachable. On Cloud Run, set THERECODE_MONGODB_URI to your "
                "Atlas connection string and allow 0.0.0.0/0 in Atlas Network Access."
            ),
        ) from exc
    yield manager.database
