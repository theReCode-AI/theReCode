from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CODETHERA_",
        extra="ignore",
    )

    app_name: str = "CodeThera"
    environment: Literal["development", "staging", "production", "test"] = "development"
    api_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default=["http://localhost:5173"])
    workspace_root: Path = Path("../workspace")
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database_name: str = "codethera"
    mongodb_server_selection_timeout_ms: int = 5000
    mongodb_connect_timeout_ms: int = 5000
    jwt_secret_key: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    credentials_encryption_key: str = "dev-encryption-key-change-in-production-32b"
    github_api_base_url: str = "https://api.github.com"
    gitlab_api_base_url: str = "https://gitlab.com/api/v4"
    scanner_timeout_seconds: int = 300
    max_fix_iterations: int = 3
    google_api_key: str = ""
    google_genai_use_vertexai: bool = False
    gemini_model: str = "gemini-2.5-flash"
    google_adk_app_name: str = "codethera"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def resolved_workspace_root(self) -> Path:
        path = self.workspace_root
        if not path.is_absolute():
            path = (Path(__file__).resolve().parents[2] / path).resolve()
        return path


settings = Settings()


def get_settings() -> Settings:
    return settings
