from app.core.config import Settings
from app.core.logging import get_logger
from app.core.security import create_access_token, hash_password, verify_password
from app.db.repositories.user_repository import UserAlreadyExistsError, UserRepository
from app.models.user import User
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse

logger = get_logger(__name__)


class InvalidCredentialsError(Exception):
    pass


class AuthService:
    """Authentication and user registration service."""

    def __init__(self, user_repository: UserRepository, app_settings: Settings) -> None:
        self._user_repository = user_repository
        self._settings = app_settings

    def register(self, payload: UserCreate) -> UserResponse:
        hashed_password = hash_password(payload.password)

        try:
            user = self._user_repository.create(
                email=payload.email,
                full_name=payload.full_name,
                hashed_password=hashed_password,
            )
        except UserAlreadyExistsError as exc:
            logger.info(
                "Registration failed: email already exists",
                extra={"email": exc.email, "stage": "auth_register"},
            )
            raise

        logger.info(
            "User registered",
            extra={"user_id": user.id, "email": user.email, "stage": "auth_register"},
        )
        return self._to_user_response(user)

    def login(self, payload: UserLogin) -> TokenResponse:
        user = self.authenticate_user(payload.email, payload.password)
        if user is None:
            logger.info(
                "Login failed",
                extra={"email": payload.email.lower(), "stage": "auth_login"},
            )
            raise InvalidCredentialsError

        token = create_access_token(
            subject=user.id,
            app_settings=self._settings,
            extra_claims={"email": user.email},
        )
        logger.info(
            "User logged in",
            extra={"user_id": user.id, "email": user.email, "stage": "auth_login"},
        )
        return TokenResponse(access_token=token)

    def authenticate_user(self, email: str, password: str) -> User | None:
        user = self._user_repository.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            return None
        return user

    def get_user_by_id(self, user_id: str) -> User | None:
        return self._user_repository.get_by_id(user_id)

    @staticmethod
    def _to_user_response(user: User) -> UserResponse:
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at,
        )
