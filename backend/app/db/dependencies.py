from collections.abc import Generator

from fastapi import Depends
from pymongo.database import Database

from app.db.mongodb import MongoDBManager, mongodb_manager


def get_mongodb_manager() -> MongoDBManager:
    return mongodb_manager


def get_database(
    manager: MongoDBManager = Depends(get_mongodb_manager),
) -> Generator[Database, None, None]:
    yield manager.database
