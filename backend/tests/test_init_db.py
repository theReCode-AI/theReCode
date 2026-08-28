from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.db.init_db import initialize_database, shutdown_database
from app.db.mongodb import MongoDBManager


@pytest.fixture
def isolated_manager() -> MongoDBManager:
    return MongoDBManager(
        Settings(
            mongodb_uri="mongodb://localhost:27017",
            mongodb_database_name="codethera_test",
        )
    )


def test_initialize_database_connects_and_indexes(
    isolated_manager: MongoDBManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect_called = False
    indexes_called = False

    def mock_connect(self: MongoDBManager) -> None:
        nonlocal connect_called
        connect_called = True
        self._client = MagicMock()  # noqa: SLF001

    def mock_ensure_indexes(self: MongoDBManager) -> None:
        nonlocal indexes_called
        indexes_called = True

    monkeypatch.setattr(MongoDBManager, "connect", mock_connect)
    monkeypatch.setattr(MongoDBManager, "ensure_indexes", mock_ensure_indexes)

    initialize_database(isolated_manager)

    assert connect_called is True
    assert indexes_called is True


def test_shutdown_database_disconnects(
    isolated_manager: MongoDBManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disconnected = False

    def mock_disconnect(self: MongoDBManager) -> None:
        nonlocal disconnected
        disconnected = True

    monkeypatch.setattr(MongoDBManager, "disconnect", mock_disconnect)

    shutdown_database(isolated_manager)

    assert disconnected is True
