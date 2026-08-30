from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from pymongo.database import Database

from app.db.dependencies import get_database, get_mongodb_manager
from app.db.mongodb import MongoDBManager


def test_get_mongodb_manager_returns_singleton() -> None:
    manager = get_mongodb_manager()
    assert isinstance(manager, MongoDBManager)


@pytest.fixture
def dependency_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    mock_manager = MagicMock(spec=MongoDBManager)
    mock_database = MagicMock(spec=Database)
    mock_database.name = "therecode_test"
    mock_manager.database = mock_database
    monkeypatch.setattr("app.db.dependencies.mongodb_manager", mock_manager)

    app = FastAPI()

    @app.get("/database")
    def read_database(database: Database = Depends(get_database)) -> dict[str, str]:
        return {"database": database.name}

    return app


async def test_get_database_dependency(dependency_app: FastAPI) -> None:
    transport = ASGITransport(app=dependency_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/database")

    assert response.status_code == 200
