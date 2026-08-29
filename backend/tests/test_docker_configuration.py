from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_docker_compose_defines_core_services() -> None:
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for service in ("mongodb:", "backend:", "frontend:"):
        assert service in compose


def test_backend_dockerfile_has_healthcheck_and_git() -> None:
    dockerfile = (REPO_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert "git" in dockerfile
    assert "CODETHERA_WORKSPACE_ROOT=/workspace" in dockerfile
    assert "--group scanners" in dockerfile
    assert "README.md" in dockerfile
    assert "COPY app ./app" in dockerfile
    assert "osv-scanner_linux_" in dockerfile
    assert "gitleaks_" in dockerfile


def test_frontend_nginx_supports_sse_proxy() -> None:
    compose_nginx = (REPO_ROOT / "frontend" / "nginx.compose.conf.template").read_text(
        encoding="utf-8"
    )
    cloud_nginx = (REPO_ROOT / "frontend" / "nginx.conf.template").read_text(encoding="utf-8")
    assert "proxy_buffering off" in compose_nginx
    assert "proxy_pass http://backend:8000" in compose_nginx
    assert "listen ${PORT}" in cloud_nginx
    assert "proxy_pass" not in cloud_nginx


def test_frontend_dockerfile_listens_on_cloud_run_port() -> None:
    dockerfile = (REPO_ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    assert "ENV PORT=8080" in dockerfile
    assert "nginx.conf.template" in dockerfile
    assert "EXPOSE 8080" in dockerfile
    assert "API_UPSTREAM" not in dockerfile
    cloud_nginx = (REPO_ROOT / "frontend" / "nginx.conf.template").read_text(encoding="utf-8")
    assert "backend:8000" not in cloud_nginx


def test_docker_env_example_uses_internal_mongodb_uri() -> None:
    env_example = (REPO_ROOT / ".env.docker.example").read_text(encoding="utf-8")
    assert "mongodb://mongodb:27017" in env_example
    assert "VITE_API_BASE_URL=/api/v1" in env_example
