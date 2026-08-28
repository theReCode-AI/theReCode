from enum import StrEnum

from pydantic import BaseModel, Field


class PackageManager(StrEnum):
    UV = "uv"
    PIP = "pip"
    POETRY = "poetry"
    PIPENV = "pipenv"
    CONDA = "conda"
    UNKNOWN = "unknown"


class ApplicationArchitecture(StrEnum):
    FASTAPI = "fastapi"
    DJANGO = "django"
    FLASK = "flask"
    CLI = "cli"
    LIBRARY = "library"
    UNKNOWN = "unknown"


class ProjectIntelligence(BaseModel):
    """Structured repository analysis produced by the Project Intelligence stage."""

    language: str = "python"
    python_version: str | None = None
    package_manager: PackageManager = PackageManager.UNKNOWN
    frameworks: list[str] = Field(default_factory=list)
    entrypoints: list[str] = Field(default_factory=list)
    source_directories: list[str] = Field(default_factory=list)
    test_directories: list[str] = Field(default_factory=list)
    dependency_files: list[str] = Field(default_factory=list)
    config_files: list[str] = Field(default_factory=list)
    docker: bool = False
    ci: bool = False
    startup_command: str | None = None
    architecture: ApplicationArchitecture = ApplicationArchitecture.UNKNOWN
    python_file_count: int = 0
    test_file_count: int = 0
