from unittest.mock import MagicMock

import pytest
from pymongo.errors import ConnectionFailure

from app.core.config import Settings
from app.db.mongodb import MongoDBManager


@pytest.fixture
def isolated_manager() -> MongoDBManager:
    return MongoDBManager(
        Settings(
            mongodb_uri="mongodb://localhost:27017",
            mongodb_database_name="codethera_test",
        )
    )


def test_ping_returns_disconnected_when_not_connected(isolated_manager: MongoDBManager) -> None:
    assert isolated_manager.ping() == "disconnected"


def test_connect_sets_client_and_pings(
    isolated_manager: MongoDBManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.admin.command.return_value = {"ok": 1}
    monkeypatch.setattr(
        "app.db.mongodb.MongoClient",
        lambda *args, **kwargs: mock_client,
    )

    isolated_manager.connect()

    assert isolated_manager.is_connected is True
    assert isolated_manager.ping() == "ok"
    mock_client.admin.command.assert_called_with("ping")


def test_ping_returns_unavailable_on_error(
    isolated_manager: MongoDBManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.admin.command.return_value = {"ok": 1}
    monkeypatch.setattr(
        "app.db.mongodb.MongoClient",
        lambda *args, **kwargs: mock_client,
    )

    isolated_manager.connect()
    mock_client.admin.command.side_effect = ConnectionFailure("connection failed")

    assert isolated_manager.ping() == "unavailable"


def test_disconnect_closes_client(
    isolated_manager: MongoDBManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.admin.command.return_value = {"ok": 1}
    monkeypatch.setattr(
        "app.db.mongodb.MongoClient",
        lambda *args, **kwargs: mock_client,
    )

    isolated_manager.connect()
    isolated_manager.disconnect()

    assert isolated_manager.is_connected is False
    mock_client.close.assert_called_once()


def test_ensure_indexes_creates_indexes(
    isolated_manager: MongoDBManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_collection = MagicMock()
    mock_database = MagicMock()
    mock_database.__getitem__.return_value = mock_collection
    mock_client = MagicMock()
    mock_client.admin.command.return_value = {"ok": 1}
    mock_client.__getitem__.return_value = mock_database
    monkeypatch.setattr(
        "app.db.mongodb.MongoClient",
        lambda *args, **kwargs: mock_client,
    )

    isolated_manager.connect()
    isolated_manager.ensure_indexes()

    assert mock_collection.create_index.call_count > 0
