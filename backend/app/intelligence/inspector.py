"""Read-only repository inspection for project intelligence."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from app.intelligence.exceptions import RepositoryEmptyError, RepositoryNotReadyError
from app.models.project_intelligence import (
    ApplicationArchitecture,
    PackageManager,
    ProjectIntelligence,
)

IGNORED_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        ".env",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        ".tox",
        "dist",
        "build",
        ".eggs",
    }
)

KNOWN_DEPENDENCY_FILES = (
    "pyproject.toml",
    "uv.lock",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements.in",
    "setup.py",
    "setup.cfg",
    "environment.yml",
    "conda.yml",
    "runtime.txt",
    ".python-version",
)

KNOWN_CONFIG_FILES = (
    ".env.example",
    ".env.template",
    "pytest.ini",
    "tox.ini",
    "ruff.toml",
    ".ruff.toml",
    "mypy.ini",
    ".flake8",
    "setup.cfg",
    "alembic.ini",
    "gunicorn.conf.py",
)

FRAMEWORK_DEPENDENCIES = {
    "fastapi": "fastapi",
    "django": "django",
    "flask": "flask",
    "starlette": "starlette",
    "celery": "celery",
    "tornado": "tornado",
    "sanic": "sanic",
    "litestar": "litestar",
    "gradio": "gradio",
    "streamlit": "streamlit",
}

PYTHON_VERSION_PATTERN = re.compile(r"(\d+\.\d+(?:\.\d+)?)")
DOCKER_PYTHON_PATTERN = re.compile(r"python[:/](\d+\.\d+(?:\.\d+)?)", re.IGNORECASE)


class RepositoryInspector:
    """Inspect a cloned repository without modifying any files."""

    def inspect(self, repository_path: Path) -> ProjectIntelligence:
        if not repository_path.exists():
            raise RepositoryNotReadyError(f"Repository path does not exist: {repository_path}")

        if not repository_path.is_dir():
            raise RepositoryNotReadyError(f"Repository path is not a directory: {repository_path}")

        if not any(repository_path.iterdir()):
            raise RepositoryEmptyError()

        pyproject = self._load_pyproject(repository_path)
        dependency_files = self._find_dependency_files(repository_path)
        config_files = self._find_config_files(repository_path)
        package_manager = self._detect_package_manager(repository_path, pyproject, dependency_files)
        python_version = self._detect_python_version(repository_path, pyproject)
        frameworks = self._detect_frameworks(repository_path, pyproject, dependency_files)
        source_directories = self._detect_source_directories(repository_path, pyproject)
        test_directories = self._detect_test_directories(repository_path)
        entrypoints = self._detect_entrypoints(repository_path, pyproject)
        docker = self._has_docker(repository_path)
        ci = self._has_ci(repository_path)
        architecture = self._detect_architecture(frameworks, entrypoints, pyproject)
        startup_command = self._infer_startup_command(
            repository_path,
            package_manager,
            frameworks,
            entrypoints,
            docker,
        )
        python_file_count, test_file_count = self._count_python_files(
            repository_path,
            test_directories,
        )

        return ProjectIntelligence(
            python_version=python_version,
            package_manager=package_manager,
            frameworks=frameworks,
            entrypoints=entrypoints,
            source_directories=source_directories,
            test_directories=test_directories,
            dependency_files=dependency_files,
            config_files=config_files,
            docker=docker,
            ci=ci,
            startup_command=startup_command,
            architecture=architecture,
            python_file_count=python_file_count,
            test_file_count=test_file_count,
        )

    def _load_pyproject(self, repository_path: Path) -> dict:
        pyproject_path = repository_path / "pyproject.toml"
        if not pyproject_path.is_file():
            return {}

        try:
            return tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return {}

    def _find_dependency_files(self, repository_path: Path) -> list[str]:
        found: list[str] = []
        for name in KNOWN_DEPENDENCY_FILES:
            if (repository_path / name).is_file():
                found.append(name)
        return sorted(found)

    def _find_config_files(self, repository_path: Path) -> list[str]:
        found: list[str] = []
        for name in KNOWN_CONFIG_FILES:
            if (repository_path / name).is_file():
                found.append(name)
        return sorted(found)

    def _detect_package_manager(
        self,
        repository_path: Path,
        pyproject: dict,
        dependency_files: list[str],
    ) -> PackageManager:
        if "uv.lock" in dependency_files or pyproject.get("tool", {}).get("uv"):
            return PackageManager.UV
        if "poetry.lock" in dependency_files or pyproject.get("tool", {}).get("poetry"):
            return PackageManager.POETRY
        if "Pipfile" in dependency_files or "Pipfile.lock" in dependency_files:
            return PackageManager.PIPENV
        if "environment.yml" in dependency_files or "conda.yml" in dependency_files:
            return PackageManager.CONDA
        if any(
            name in dependency_files
            for name in ("requirements.txt", "pyproject.toml", "setup.py", "setup.cfg")
        ):
            return PackageManager.PIP
        return PackageManager.UNKNOWN

    def _detect_python_version(self, repository_path: Path, pyproject: dict) -> str | None:
        python_version_file = repository_path / ".python-version"
        if python_version_file.is_file():
            version = python_version_file.read_text(encoding="utf-8").strip()
            if version:
                return version

        requires_python = pyproject.get("project", {}).get("requires-python")
        if isinstance(requires_python, str):
            match = PYTHON_VERSION_PATTERN.search(requires_python)
            if match:
                return match.group(1)

        runtime_file = repository_path / "runtime.txt"
        if runtime_file.is_file():
            match = PYTHON_VERSION_PATTERN.search(runtime_file.read_text(encoding="utf-8"))
            if match:
                return match.group(1)

        dockerfile = repository_path / "Dockerfile"
        if dockerfile.is_file():
            match = DOCKER_PYTHON_PATTERN.search(dockerfile.read_text(encoding="utf-8"))
            if match:
                return match.group(1)

        return None

    def _detect_frameworks(
        self,
        repository_path: Path,
        pyproject: dict,
        dependency_files: list[str],
    ) -> list[str]:
        dependencies = self._collect_dependency_names(repository_path, pyproject, dependency_files)
        frameworks = [
            label
            for dependency, label in FRAMEWORK_DEPENDENCIES.items()
            if dependency in dependencies
        ]
        return sorted(set(frameworks))

    def _collect_dependency_names(
        self,
        repository_path: Path,
        pyproject: dict,
        dependency_files: list[str],
    ) -> set[str]:
        names: set[str] = set()

        project_deps = pyproject.get("project", {}).get("dependencies", [])
        if isinstance(project_deps, list):
            names.update(self._normalize_dependency_name(dep) for dep in project_deps)

        optional_deps = pyproject.get("project", {}).get("optional-dependencies", {})
        if isinstance(optional_deps, dict):
            for deps in optional_deps.values():
                if isinstance(deps, list):
                    names.update(self._normalize_dependency_name(dep) for dep in deps)

        poetry_deps = pyproject.get("tool", {}).get("poetry", {}).get("dependencies", {})
        if isinstance(poetry_deps, dict):
            names.update(name.lower() for name in poetry_deps if name.lower() != "python")

        if "requirements.txt" in dependency_files:
            requirements_path = repository_path / "requirements.txt"
            for line in requirements_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                names.add(self._normalize_dependency_name(line))

        return names

    @staticmethod
    def _normalize_dependency_name(dependency: str) -> str:
        value = dependency.strip().lower()
        for separator in ("[", "==", ">=", "<=", "~=", "!=", "<", ">", " "):
            if separator in value:
                value = value.split(separator, 1)[0]
        return value

    def _detect_source_directories(self, repository_path: Path, pyproject: dict) -> list[str]:
        candidates: list[str] = []

        packages = pyproject.get("tool", {}).get("poetry", {}).get("packages")
        if isinstance(packages, list):
            for package in packages:
                if isinstance(package, dict) and package.get("include"):
                    candidates.append(str(package["include"]))

        for name in ("src", "app", "lib"):
            path = repository_path / name
            if path.is_dir() and self._contains_python_files(path):
                candidates.append(name)

        if not candidates:
            for path in repository_path.iterdir():
                if not path.is_dir() or path.name in IGNORED_DIR_NAMES:
                    continue
                if self._contains_python_files(path) and not self._looks_like_test_directory(
                    path.name,
                ):
                    candidates.append(path.name)

        return sorted(set(candidates))

    def _detect_test_directories(self, repository_path: Path) -> list[str]:
        candidates: list[str] = []
        for name in ("tests", "test"):
            path = repository_path / name
            if path.is_dir():
                candidates.append(name)

        if (repository_path / "conftest.py").is_file() and "." not in candidates:
            candidates.append(".")

        return sorted(set(candidates))

    def _detect_entrypoints(self, repository_path: Path, pyproject: dict) -> list[str]:
        entrypoints: list[str] = []

        scripts = pyproject.get("project", {}).get("scripts", {})
        if isinstance(scripts, dict):
            for script_name, target in scripts.items():
                entrypoints.append(f"{script_name}={target}")

        poetry_scripts = pyproject.get("tool", {}).get("poetry", {}).get("scripts", {})
        if isinstance(poetry_scripts, dict):
            for script_name, target in poetry_scripts.items():
                entrypoints.append(f"{script_name}={target}")

        for relative_path in self._iter_python_files(repository_path):
            if relative_path.name in {"main.py", "app.py", "__main__.py"}:
                entrypoints.append(relative_path.as_posix())

        return sorted(set(entrypoints))

    def _has_docker(self, repository_path: Path) -> bool:
        return (repository_path / "Dockerfile").is_file() or (
            repository_path / "docker-compose.yml"
        ).is_file() or (repository_path / "compose.yml").is_file()

    def _has_ci(self, repository_path: Path) -> bool:
        if (repository_path / ".gitlab-ci.yml").is_file():
            return True
        if (repository_path / "Jenkinsfile").is_file():
            return True
        github_workflows = repository_path / ".github" / "workflows"
        return github_workflows.is_dir() and any(github_workflows.iterdir())

    def _detect_architecture(
        self,
        frameworks: list[str],
        entrypoints: list[str],
        pyproject: dict,
    ) -> ApplicationArchitecture:
        if "django" in frameworks:
            return ApplicationArchitecture.DJANGO
        if "fastapi" in frameworks or "starlette" in frameworks or "litestar" in frameworks:
            return ApplicationArchitecture.FASTAPI
        if "flask" in frameworks or "sanic" in frameworks:
            return ApplicationArchitecture.FLASK

        scripts = pyproject.get("project", {}).get("scripts", {})
        if isinstance(scripts, dict) and scripts:
            return ApplicationArchitecture.CLI

        if any("=" in entrypoint for entrypoint in entrypoints):
            return ApplicationArchitecture.CLI

        if frameworks:
            return ApplicationArchitecture.LIBRARY

        return ApplicationArchitecture.UNKNOWN

    def _infer_startup_command(
        self,
        repository_path: Path,
        package_manager: PackageManager,
        frameworks: list[str],
        entrypoints: list[str],
        docker: bool,
    ) -> str | None:
        if docker:
            docker_command = self._read_docker_startup_command(repository_path)
            if docker_command:
                return docker_command

        if "fastapi" in frameworks:
            module = self._find_uvicorn_target(repository_path, entrypoints)
            if module:
                return self._prefix_run_command(package_manager, f"uvicorn {module}")

        if "django" in frameworks:
            return self._prefix_run_command(package_manager, "python manage.py runserver")

        if "flask" in frameworks:
            return self._prefix_run_command(package_manager, "flask run")

        script_entrypoints = [entry for entry in entrypoints if "=" in entry]
        if script_entrypoints:
            script_name = script_entrypoints[0].split("=", 1)[0]
            return self._prefix_run_command(package_manager, script_name)

        main_files = [entry for entry in entrypoints if entry.endswith(("main.py", "app.py"))]
        if main_files:
            return self._prefix_run_command(package_manager, f"python {main_files[0]}")

        return None

    def _read_docker_startup_command(self, repository_path: Path) -> str | None:
        dockerfile = repository_path / "Dockerfile"
        if not dockerfile.is_file():
            return None

        cmd_lines: list[str] = []
        for line in dockerfile.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("CMD ") or stripped.upper().startswith("ENTRYPOINT "):
                cmd_lines.append(stripped.split(" ", 1)[1])

        if not cmd_lines:
            return None

        return " ".join(cmd_lines).strip("[]\"'")

    def _find_uvicorn_target(self, repository_path: Path, entrypoints: list[str]) -> str | None:
        for entrypoint in entrypoints:
            if entrypoint.endswith("main.py"):
                module_path = Path(entrypoint)
                if module_path.name == "main.py":
                    parent = module_path.parent.as_posix()
                    if parent == ".":
                        return "main:app"
                    return f"{parent.replace('/', '.')}.main:app"

        for relative_path in self._iter_python_files(repository_path):
            if relative_path.name != "main.py":
                continue
            content = (repository_path / relative_path).read_text(encoding="utf-8", errors="ignore")
            if "FastAPI(" in content or "app = FastAPI" in content:
                parent = relative_path.parent.as_posix()
                if parent == ".":
                    return "main:app"
                return f"{parent.replace('/', '.')}.main:app"

        return None

    @staticmethod
    def _prefix_run_command(package_manager: PackageManager, command: str) -> str:
        if package_manager == PackageManager.UV:
            return f"uv run {command}"
        if package_manager == PackageManager.POETRY:
            return f"poetry run {command}"
        if package_manager == PackageManager.PIPENV:
            return f"pipenv run {command}"
        return command

    def _count_python_files(
        self,
        repository_path: Path,
        test_directories: list[str],
    ) -> tuple[int, int]:
        python_files = list(self._iter_python_files(repository_path))
        test_files = [
            path
            for path in python_files
            if self._is_test_file(path, test_directories)
        ]
        return len(python_files), len(test_files)

    def _iter_python_files(self, repository_path: Path) -> list[Path]:
        files: list[Path] = []
        for path in repository_path.rglob("*.py"):
            if any(part in IGNORED_DIR_NAMES for part in path.relative_to(repository_path).parts):
                continue
            files.append(path.relative_to(repository_path))
        return files

    def _contains_python_files(self, directory: Path) -> bool:
        return any(directory.rglob("*.py"))

    @staticmethod
    def _looks_like_test_directory(name: str) -> bool:
        return name in {"tests", "test"} or name.startswith("test_")

    @staticmethod
    def _is_test_file(relative_path: Path, test_directories: list[str]) -> bool:
        parts = relative_path.parts
        if parts and parts[0] in {"tests", "test"}:
            return True
        return relative_path.name.startswith("test_") or relative_path.name.endswith("_test.py")
