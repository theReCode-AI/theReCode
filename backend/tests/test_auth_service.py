import pytest
from bson import ObjectId

from app.core.config import Settings
from app.core.security import hash_password
from app.db.repositories.user_repository import UserRepository
from app.models.user import User
from app.schemas.auth import UserCreate, UserLogin
from app.services.auth_service import AuthService, InvalidCredentialsError


class InMemoryUserRepository(UserRepository):
    """In-memory user repository for tests."""

    def __init__(self) -> None:
        self._users: dict[str, dict] = {}

    def get_by_email(self, email: str) -> User | None:
        for document in self._users.values():
            if document["email"] == email.lower():
                return User.from_document(document.copy())
        return None

    def get_by_id(self, user_id: str) -> User | None:
        document = self._users.get(user_id)
        if document is None:
            return None
        return User.from_document(document.copy())

    def create(self, email: str, full_name: str, hashed_password: str) -> User:
        if self.get_by_email(email) is not None:
            from app.db.repositories.user_repository import UserAlreadyExistsError

            raise UserAlreadyExistsError(email)

        user_id = str(ObjectId())
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        document = {
            "_id": ObjectId(user_id),
            "email": email.lower(),
            "full_name": full_name,
            "hashed_password": hashed_password,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        self._users[user_id] = document
        return User.from_document(document.copy())


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        environment="test",
        jwt_secret_key="test-secret-key-with-sufficient-length",
        jwt_access_token_expire_minutes=30,
    )


@pytest.fixture
def user_repository() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
def auth_service(user_repository: InMemoryUserRepository, test_settings: Settings) -> AuthService:
    return AuthService(user_repository=user_repository, app_settings=test_settings)


@pytest.fixture
def registered_user(auth_service: AuthService) -> User:
    user_response = auth_service.register(
        UserCreate(email="user@example.com", full_name="Test User", password="password123"),
    )
    user = auth_service.get_user_by_id(user_response.id)
    assert user is not None
    return user


def test_register_creates_user(auth_service: AuthService) -> None:
    user = auth_service.register(
        UserCreate(email="new@example.com", full_name="New User", password="password123"),
    )

    assert user.email == "new@example.com"
    assert user.full_name == "New User"
    assert user.is_active is True


def test_register_duplicate_email_raises(auth_service: AuthService, registered_user: User) -> None:
    from app.db.repositories.user_repository import UserAlreadyExistsError

    with pytest.raises(UserAlreadyExistsError):
        auth_service.register(
            UserCreate(
                email=registered_user.email,
                full_name="Another User",
                password="password123",
            ),
        )


def test_login_returns_token(auth_service: AuthService, registered_user: User) -> None:
    token = auth_service.login(
        UserLogin(email=registered_user.email, password="password123"),
    )

    assert token.access_token
    assert token.token_type == "bearer"


def test_login_invalid_password_raises(auth_service: AuthService, registered_user: User) -> None:
    with pytest.raises(InvalidCredentialsError):
        auth_service.login(
            UserLogin(email=registered_user.email, password="wrong-password"),
        )


def test_authenticate_user_success(auth_service: AuthService, registered_user: User) -> None:
    user = auth_service.authenticate_user(registered_user.email, "password123")

    assert user is not None
    assert user.id == registered_user.id


def test_hash_password_roundtrip() -> None:
    hashed = hash_password("password123")
    assert hashed != "password123"
    assert hashed.startswith("$2")
