import pytest
from pymongo.errors import ServerSelectionTimeoutError

from app.core.config import Settings
from app.db.mongodb import MongoDBManager
from app.db.repositories.linked_repository_repository import LinkedRepositoryRepository
from app.db.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, RepositoryCreate
from app.services.project_service import ProjectService


@pytest.mark.integration
def test_project_flow_with_mongodb() -> None:
    settings = Settings(mongodb_database_name="codethera_projects_test")
    manager = MongoDBManager(settings)

    try:
        manager.connect()
    except ServerSelectionTimeoutError:
        pytest.skip("MongoDB is not available")

    try:
        database = manager.database
        database.drop_collection("projects")
        database.drop_collection("repositories")
        manager.ensure_indexes()

        user_id = "674f1f77bcf86cd799439011"
        service = ProjectService(
            project_repository=ProjectRepository(database),
            linked_repository_repository=LinkedRepositoryRepository(database),
        )

        project = service.create_project(user_id, ProjectCreate(name="Integration Project"))
        repository = service.create_repository(
            user_id,
            project.id,
            RepositoryCreate(provider="github", full_name="org/integration"),
        )
        projects = service.list_projects(user_id)

        assert len(projects) == 1
        assert repository.project_id == project.id
    finally:
        manager.disconnect()
