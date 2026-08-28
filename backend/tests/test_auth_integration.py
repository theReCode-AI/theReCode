import pytest
from pymongo.errors import ServerSelectionTimeoutError

from app.core.config import Settings
from app.db.mongodb import MongoDBManager
from app.db.repositories.user_repository import UserRepository
from app.schemas.auth import UserCreate, UserLogin
from app.services.auth_service import AuthService


@pytest.mark.integration
def test_auth_flow_with_mongodb() -> None:
    settings = Settings(mongodb_database_name="codethera_auth_test")
    manager = MongoDBManager(settings)

    try:
        manager.connect()
    except ServerSelectionTimeoutError:
        pytest.skip("MongoDB is not available")

    try:
        database = manager.database
        database.drop_collection("users")
        manager.ensure_indexes()

        repository = UserRepository(database)
        auth_service = AuthService(
            user_repository=repository,
            app_settings=Settings(
                environment="test",
                jwt_secret_key="integration-test-secret-with-sufficient-length",
            ),
        )

        user = auth_service.register(
            UserCreate(
                email="integration@example.com",
                full_name="Integration User",
                password="password123",
            ),
        )
        token = auth_service.login(
            UserLogin(email="integration@example.com", password="password123"),
        )
        loaded_user = auth_service.get_user_by_id(user.id)

        assert token.access_token
        assert loaded_user is not None
        assert loaded_user.email == "integration@example.com"
    finally:
        manager.disconnect()
