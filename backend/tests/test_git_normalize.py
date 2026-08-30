import pytest

from app.git.normalize import normalize_repository_full_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("codezerro/langfuse-master", "codezerro/langfuse-master"),
        ("codezerro/langfuse-master.git", "codezerro/langfuse-master"),
        ("https://github.com/codezerro/langfuse-master.git", "codezerro/langfuse-master"),
        ("https://github.com/codezerro/langfuse-master", "codezerro/langfuse-master"),
        ("github.com/codezerro/langfuse-master", "codezerro/langfuse-master"),
        ("git@github.com:codezerro/langfuse-master.git", "codezerro/langfuse-master"),
    ],
)
def test_normalize_github_repository_full_name(raw: str, expected: str) -> None:
    assert normalize_repository_full_name("github", raw) == expected


def test_normalize_gitlab_repository_url() -> None:
    assert (
        normalize_repository_full_name("gitlab", "https://gitlab.com/group/subgroup/project.git")
        == "group/subgroup/project"
    )
