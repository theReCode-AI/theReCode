import pytest
from httpx import AsyncClient

from app.db.mongodb import MongoDBManager


async def test_liveness(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "codethera-backend"


async def test_readiness_when_mongodb_connected(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["mongodb"] == "ok"


async def test_readiness_when_mongodb_unavailable(
    client: AsyncClient,
    manager: MongoDBManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager, "ping", lambda: "unavailable")

    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["checks"]["mongodb"] == "unavailable"


async def test_root(client: AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "CodeThera"
    assert data["health"] == "/api/v1/health"
