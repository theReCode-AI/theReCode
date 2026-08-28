import shutil
from pathlib import Path

import pytest

from app.intelligence import RepositoryEmptyError, RepositoryInspector, RepositoryNotReadyError
from app.models.project_intelligence import ApplicationArchitecture, PackageManager

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_FASTAPI_PROJECT = FIXTURES_DIR / "sample_fastapi_project"


@pytest.fixture
def inspector() -> RepositoryInspector:
    return RepositoryInspector()


def test_inspect_fastapi_project(inspector: RepositoryInspector) -> None:
    intelligence = inspector.inspect(SAMPLE_FASTAPI_PROJECT)

    assert intelligence.language == "python"
    assert intelligence.python_version == "3.12"
    assert intelligence.package_manager == PackageManager.UV
    assert "fastapi" in intelligence.frameworks
    assert intelligence.architecture == ApplicationArchitecture.FASTAPI
    assert "src" in intelligence.source_directories
    assert "tests" in intelligence.test_directories
    assert "pyproject.toml" in intelligence.dependency_files
    assert intelligence.docker is True
    assert intelligence.ci is True
    assert intelligence.startup_command is not None
    assert "uvicorn" in intelligence.startup_command
    assert intelligence.python_file_count >= 2
    assert intelligence.test_file_count >= 1


def test_inspect_missing_repository(inspector: RepositoryInspector, tmp_path: Path) -> None:
    with pytest.raises(RepositoryNotReadyError):
        inspector.inspect(tmp_path / "missing")


def test_inspect_empty_repository(inspector: RepositoryInspector, tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(RepositoryEmptyError):
        inspector.inspect(empty_dir)


def test_inspect_poetry_project(inspector: RepositoryInspector, tmp_path: Path) -> None:
    project_dir = tmp_path / "poetry-app"
    project_dir.mkdir()
    (project_dir / "pyproject.toml").write_text(
        """
[tool.poetry]
name = "poetry-app"
version = "0.1.0"
packages = [{ include = "poetry_app" }]

[tool.poetry.dependencies]
python = "^3.11"
flask = "^3.0.0"
""".strip(),
        encoding="utf-8",
    )
    (project_dir / "poetry.lock").write_text("", encoding="utf-8")
    app_dir = project_dir / "poetry_app"
    app_dir.mkdir()
    (app_dir / "__init__.py").write_text("", encoding="utf-8")
    (app_dir / "app.py").write_text(
        "from flask import Flask\napp = Flask(__name__)\n",
        encoding="utf-8",
    )

    intelligence = inspector.inspect(project_dir)

    assert intelligence.package_manager == PackageManager.POETRY
    assert "flask" in intelligence.frameworks
    assert intelligence.architecture == ApplicationArchitecture.FLASK


def test_inspect_does_not_modify_repository(inspector: RepositoryInspector, tmp_path: Path) -> None:
    source = SAMPLE_FASTAPI_PROJECT
    destination = tmp_path / "copy"
    shutil.copytree(source, destination)

    before = {
        path.relative_to(destination): path.stat().st_mtime_ns
        for path in destination.rglob("*")
        if path.is_file()
    }

    inspector.inspect(destination)

    after = {
        path.relative_to(destination): path.stat().st_mtime_ns
        for path in destination.rglob("*")
        if path.is_file()
    }

    assert before == after
