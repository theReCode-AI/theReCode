import pytest
from httpx import AsyncClient

from app.api.dependencies import (
    get_auth_service,
    get_linked_repository_repository,
    get_project_repository,
    get_project_service,
    get_settings,
    get_user_repository,
)
from app.core.config import Settings
from app.main import create_app
from app.services.auth_service import AuthService
from app.services.project_service import ProjectService
from tests.test_auth_service import InMemoryUserRepository
from tests.test_project_service import (
    InMemoryLinkedRepositoryRepository,
    InMemoryProjectRepository,
)


@pytest.fixture
def user_repository() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
def project_repository() -> InMemoryProjectRepository:
    return InMemoryProjectRepository()


@pytest.fixture
def linked_repository_repository() -> InMemoryLinkedRepositoryRepository:
    return InMemoryLinkedRepositoryRepository()


@pytest.fixture
async def authenticated_client(
    mock_mongodb_lifecycle,
    user_repository: InMemoryUserRepository,
    project_repository: InMemoryProjectRepository,
    linked_repository_repository: InMemoryLinkedRepositoryRepository,
) -> AsyncClient:
    from httpx import ASGITransport

    app = create_app()
    settings = Settings(
        environment="test",
        jwt_secret_key="test-secret-key-with-sufficient-length",
        jwt_access_token_expire_minutes=30,
    )
    auth_service = AuthService(user_repository=user_repository, app_settings=settings)
    project_service = ProjectService(
        project_repository=project_repository,
        linked_repository_repository=linked_repository_repository,
    )

    app.dependency_overrides[get_user_repository] = lambda: user_repository
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_project_repository] = lambda: project_repository
    app.dependency_overrides[get_linked_repository_repository] = (
        lambda: linked_repository_repository
    )
    app.dependency_overrides[get_project_service] = lambda: project_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Project User", "password": "password123"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    return response.json()["access_token"]


async def test_projects_require_authentication(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/api/v1/projects")
    assert response.status_code == 401


async def test_project_crud_flow(authenticated_client: AsyncClient) -> None:
    token = await _register_and_login(authenticated_client, "projects@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await authenticated_client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "My Project", "description": "Test project"},
    )
    assert create_response.status_code == 201
    project = create_response.json()

    list_response = await authenticated_client.get("/api/v1/projects", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = await authenticated_client.get(
        f"/api/v1/projects/{project['id']}",
        headers=headers,
    )
    assert get_response.status_code == 200

    patch_response = await authenticated_client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=headers,
        json={"name": "Renamed Project"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["name"] == "Renamed Project"

    delete_response = await authenticated_client.delete(
        f"/api/v1/projects/{project['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 204


async def test_other_user_cannot_access_project(authenticated_client: AsyncClient) -> None:
    owner_token = await _register_and_login(authenticated_client, "owner@example.com")
    other_token = await _register_and_login(authenticated_client, "other@example.com")

    create_response = await authenticated_client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Owner Project"},
    )
    project_id = create_response.json()["id"]

    response = await authenticated_client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 404


async def test_repository_crud_flow(authenticated_client: AsyncClient) -> None:
    token = await _register_and_login(authenticated_client, "repos@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    project_id = (
        await authenticated_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Repo Project"},
        )
    ).json()["id"]

    create_repo = await authenticated_client.post(
        f"/api/v1/projects/{project_id}/repositories",
        headers=headers,
        json={
            "provider": "github",
            "full_name": "org/service",
            "default_branch": "main",
        },
    )
    assert create_repo.status_code == 201
    repository = create_repo.json()

    list_repos = await authenticated_client.get(
        f"/api/v1/projects/{project_id}/repositories",
        headers=headers,
    )
    assert list_repos.status_code == 200
    assert len(list_repos.json()) == 1

    get_repo = await authenticated_client.get(
        f"/api/v1/projects/{project_id}/repositories/{repository['id']}",
        headers=headers,
    )
    assert get_repo.status_code == 200

    patch_repo = await authenticated_client.patch(
        f"/api/v1/projects/{project_id}/repositories/{repository['id']}",
        headers=headers,
        json={"default_branch": "develop"},
    )
    assert patch_repo.status_code == 200
    assert patch_repo.json()["default_branch"] == "develop"

    delete_repo = await authenticated_client.delete(
        f"/api/v1/projects/{project_id}/repositories/{repository['id']}",
        headers=headers,
    )
    assert delete_repo.status_code == 204
