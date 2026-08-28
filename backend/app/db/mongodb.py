from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.config import Settings, settings
from app.core.logging import get_logger
from app.db.indexes import INDEX_DEFINITIONS

logger = get_logger(__name__)


class MongoDBManager:
    """Manage the PyMongo client lifecycle and database access."""

    def __init__(self, app_settings: Settings) -> None:
        self._settings = app_settings
        self._client: MongoClient | None = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def connect(self) -> None:
        if self._client is not None:
            return

        self._client = MongoClient(
            self._settings.mongodb_uri,
            serverSelectionTimeoutMS=self._settings.mongodb_server_selection_timeout_ms,
            connectTimeoutMS=self._settings.mongodb_connect_timeout_ms,
        )
        self._client.admin.command("ping")
        logger.info(
            "Connected to MongoDB",
            extra={
                "database": self._settings.mongodb_database_name,
                "stage": "mongodb_connect",
            },
        )

    def disconnect(self) -> None:
        if self._client is None:
            return

        self._client.close()
        self._client = None
        logger.info("Disconnected from MongoDB", extra={"stage": "mongodb_disconnect"})

    @property
    def database_name(self) -> str:
        return self._settings.mongodb_database_name

    @property
    def client(self) -> MongoClient:
        if self._client is None:
            raise RuntimeError("MongoDB client is not connected")
        return self._client

    @property
    def database(self) -> Database:
        return self.client[self.database_name]

    def ping(self) -> str:
        if self._client is None:
            return "disconnected"

        try:
            self._client.admin.command("ping")
            return "ok"
        except PyMongoError:
            logger.exception(
                "MongoDB ping failed",
                extra={"stage": "mongodb_ping"},
            )
            return "unavailable"

    def ensure_indexes(self) -> None:
        database = self.database
        for collection_name, indexes in INDEX_DEFINITIONS.items():
            collection = database[collection_name]
            for index in indexes:
                collection.create_index(index.fields, **index.options)

        logger.info(
            "Ensured MongoDB indexes",
            extra={
                "collections": len(INDEX_DEFINITIONS),
                "stage": "mongodb_indexes",
            },
        )


mongodb_manager = MongoDBManager(settings)
