import pytest
from httpx import AsyncClient

from app.api.dependencies import get_auth_service, get_user_repository
from app.core.config import Settings, get_settings
from app.main import create_app
from app.services.auth_service import AuthService
from tests.test_auth_service import InMemoryUserRepository


@pytest.fixture
def auth_repository() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
async def auth_client(
    mock_mongodb_lifecycle,
    auth_repository: InMemoryUserRepository,
) -> AsyncClient:
    app = create_app()
    settings = Settings(
        environment="test",
        jwt_secret_key="test-secret-key-with-sufficient-length",
        jwt_access_token_expire_minutes=30,
    )
    auth_service = AuthService(user_repository=auth_repository, app_settings=settings)

    app.dependency_overrides[get_user_repository] = lambda: auth_repository
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_settings] = lambda: settings

    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()


async def test_register_endpoint(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "api@example.com",
            "full_name": "API User",
            "password": "password123",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "api@example.com"
    assert data["full_name"] == "API User"
    assert "id" in data


async def test_register_duplicate_returns_409(auth_client: AsyncClient) -> None:
    payload = {
        "email": "dup@example.com",
        "full_name": "Dup User",
        "password": "password123",
    }
    await auth_client.post("/api/v1/auth/register", json=payload)
    response = await auth_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 409


async def test_login_endpoint(auth_client: AsyncClient) -> None:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@example.com",
            "full_name": "Login User",
            "password": "password123",
        },
    )

    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"


async def test_login_invalid_credentials_returns_401(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "password123"},
    )

    assert response.status_code == 401


async def test_me_endpoint_requires_auth(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/api/v1/auth/me")

    assert response.status_code == 401


async def test_me_endpoint_returns_current_user(auth_client: AsyncClient) -> None:
    register_response = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "me@example.com",
            "full_name": "Me User",
            "password": "password123",
        },
    )
    login_response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "me@example.com", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    response = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@example.com"
    assert data["id"] == register_response.json()["id"]
