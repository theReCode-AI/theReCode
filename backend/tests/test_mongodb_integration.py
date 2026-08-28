import pytest
from pymongo.errors import ServerSelectionTimeoutError

from app.core.config import settings
from app.db.mongodb import MongoDBManager


@pytest.mark.integration
def test_mongodb_integration_ping() -> None:
    manager = MongoDBManager(settings)

    try:
        manager.connect()
    except ServerSelectionTimeoutError:
        pytest.skip("MongoDB is not available")

    try:
        assert manager.ping() == "ok"
    finally:
        manager.disconnect()
