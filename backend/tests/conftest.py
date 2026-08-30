from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.mongodb import MongoDBManager, mongodb_manager
from app.main import create_app


@pytest.fixture
def mock_mongodb_lifecycle(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock_client = MagicMock()
    mock_client.admin.command.return_value = {"ok": 1}

    def mock_connect(self: MongoDBManager) -> None:
        self._client = mock_client  # noqa: SLF001

    def mock_disconnect(self: MongoDBManager) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None  # noqa: SLF001

    monkeypatch.setattr(MongoDBManager, "connect", mock_connect)
    monkeypatch.setattr(MongoDBManager, "disconnect", mock_disconnect)
    monkeypatch.setattr(MongoDBManager, "ensure_indexes", lambda self: None)
    return mock_client


@pytest.fixture
async def client(mock_mongodb_lifecycle: MagicMock) -> AsyncClient:
    mongodb_manager.disconnect()
    mongodb_manager.connect()
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    mongodb_manager.disconnect()


@pytest.fixture
def manager() -> MongoDBManager:
    return mongodb_manager
