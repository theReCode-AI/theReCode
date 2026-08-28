from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_docker_compose_defines_core_services() -> None:
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for service in ("mongodb:", "backend:", "frontend:"):
        assert service in compose


def test_backend_dockerfile_has_healthcheck_and_git() -> None:
    dockerfile = (REPO_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert "HEALTHCHECK" in dockerfile
    assert "git" in dockerfile
    assert "CODETHERA_WORKSPACE_ROOT=/workspace" in dockerfile
    assert "urllib.request" in dockerfile


def test_frontend_nginx_supports_sse_proxy() -> None:
    nginx = (REPO_ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    assert "proxy_buffering off" in nginx
    assert "proxy_pass http://backend:8000" in nginx


def test_docker_env_example_uses_internal_mongodb_uri() -> None:
    env_example = (REPO_ROOT / ".env.docker.example").read_text(encoding="utf-8")
    assert "mongodb://mongodb:27017" in env_example
    assert "VITE_API_BASE_URL=/api/v1" in env_example
