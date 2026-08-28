from pymongo.collection import Collection
from pymongo.database import Database


class BaseRepository:
    """Base repository for MongoDB collection access."""

    collection_name: str

    def __init__(self, database: Database) -> None:
        self._database = database

    @property
    def collection(self) -> Collection:
        return self._database[self.collection_name]
