from app.core.logging import get_logger
from app.db.mongodb import MongoDBManager

logger = get_logger(__name__)


def initialize_database(manager: MongoDBManager) -> None:
    """Connect to MongoDB and ensure required indexes exist.

    Failures are logged but do not abort process startup so Cloud Run can bind
    to PORT. Set CODETHERA_MONGODB_URI to a reachable host (e.g. Atlas).
    """
    logger.info(
        "Initializing database",
        extra={
            "database": manager.database_name,
            "stage": "database_init",
        },
    )
    try:
        manager.connect()
        manager.ensure_indexes()
    except Exception:
        logger.exception(
            "MongoDB unavailable at startup. "
            "Set CODETHERA_MONGODB_URI to a reachable instance "
            "(localhost will not work on Cloud Run).",
            extra={
                "database": manager.database_name,
                "stage": "database_init",
            },
        )
        return

    logger.info(
        "Database initialized",
        extra={
            "database": manager.database_name,
            "stage": "database_init",
        },
    )


def shutdown_database(manager: MongoDBManager) -> None:
    """Close the MongoDB client."""
    manager.disconnect()
    logger.info("Database connection closed", extra={"stage": "database_shutdown"})
