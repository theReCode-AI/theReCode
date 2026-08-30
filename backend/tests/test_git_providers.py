from pathlib import Path
from unittest.mock import MagicMock, patch

from app.git.providers import GitHubProvider, GitLabProvider, GitProviderFactory


def test_github_validate_repository_success() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "full_name": "org/repo",
        "default_branch": "main",
        "clone_url": "https://github.com/org/repo.git",
        "html_url": "https://github.com/org/repo",
    }
    mock_client = MagicMock()
    mock_client.get.return_value = mock_response

    provider = GitHubProvider("https://api.github.com", mock_client)
    result = provider.validate_repository(
        "https://github.com/org/repo.git",
        "token",
    )

    assert result.valid is True
    assert result.default_branch == "main"
    assert result.clone_url.endswith(".git")
    mock_client.get.assert_called_once_with(
        "https://api.github.com/repos/org/repo",
        headers={
            "Authorization": "Bearer token",
            "Accept": "application/vnd.github+json",
        },
    )


def test_github_validate_repository_not_found() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_client = MagicMock()
    mock_client.get.return_value = mock_response

    provider = GitHubProvider("https://api.github.com", mock_client)
    result = provider.validate_repository("org/missing", "token")

    assert result.valid is False


def test_gitlab_validate_repository_success() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "path_with_namespace": "group/project",
        "default_branch": "main",
        "http_url_to_repo": "https://gitlab.com/group/project.git",
        "web_url": "https://gitlab.com/group/project",
    }
    mock_client = MagicMock()
    mock_client.get.return_value = mock_response

    provider = GitLabProvider("https://gitlab.com/api/v4", mock_client)
    result = provider.validate_repository("group/project", "token")

    assert result.valid is True
    assert result.full_name == "group/project"


@patch("app.git.providers.subprocess.run")
def test_github_clone_repository(mock_run, tmp_path: Path) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    mock_client = MagicMock()

    provider = GitHubProvider("https://api.github.com", mock_client)
    destination = tmp_path / "repo"

    with patch.object(provider, "get_commit", return_value="abc123"):
        result = provider.clone_repository("org/repo", "main", "token", destination)

    assert result.success is True
    assert result.commit_sha == "abc123"
    mock_run.assert_called_once()


def test_factory_returns_providers() -> None:
    factory = GitProviderFactory("https://api.github.com", "https://gitlab.com/api/v4")

    assert factory.get_provider("github").provider == "github"
    assert factory.get_provider("gitlab").provider == "gitlab"


def test_github_create_pull_request_success() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.content = b'{"html_url":"https://github.com/org/repo/pull/1","number":1}'
    mock_response.json.return_value = {
        "html_url": "https://github.com/org/repo/pull/1",
        "number": 1,
    }
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response

    provider = GitHubProvider("https://api.github.com", mock_client)
    result = provider.create_pull_request(
        "org/repo",
        "agent/run",
        "main",
        "Title",
        "Body",
        "token",
    )

    assert result.success is True
    assert result.url == "https://github.com/org/repo/pull/1"
    assert result.number == 1
