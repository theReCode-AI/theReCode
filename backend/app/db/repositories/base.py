from bson import ObjectId
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

    def replace_one_preserving_id(
        self,
        *,
        filter_query: dict,
        document: dict,
        new_id: str,
    ) -> str:
        """Replace or insert a document without altering an existing MongoDB _id."""
        existing = self.collection.find_one(filter_query)
        preserved_id = existing["_id"] if existing is not None else ObjectId(new_id)
        document["_id"] = preserved_id
        self.collection.replace_one(filter_query, document, upsert=True)
        return str(preserved_id)
