"""Normalize user-supplied repository identifiers to provider full names."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.models.repository import GitProvider

_SSH_REMOTE_PATTERN = re.compile(r"^git@[^:]+:(.+?)(?:\.git)?/?$")


def normalize_repository_full_name(provider: GitProvider, raw: str) -> str:
    """Convert owner/repo, URLs, or SSH remotes to a provider full name."""
    value = raw.strip()
    if not value:
        raise ValueError("Repository name is required")

    ssh_match = _SSH_REMOTE_PATTERN.match(value)
    if ssh_match:
        return _strip_git_suffix(ssh_match.group(1).strip("/"))

    if _looks_like_url(value):
        parsed = urlparse(_ensure_scheme(value))
        host = (parsed.netloc or "").lower()
        _validate_host(provider, host)
        path = _strip_git_suffix(parsed.path.strip("/"))
        if not path:
            raise ValueError("Invalid repository URL")
        return path

    return _strip_git_suffix(value.rstrip("/"))


def _looks_like_url(value: str) -> bool:
    return "://" in value or value.startswith(("github.com/", "www.github.com/", "gitlab.com/", "www.gitlab.com/"))


def _ensure_scheme(value: str) -> str:
    if value.startswith(("http://", "https://", "git://", "ssh://")):
        return value
    return f"https://{value}"


def _validate_host(provider: GitProvider, host: str) -> None:
    if provider == "github" and host not in {"github.com", "www.github.com"}:
        raise ValueError("GitHub repository URL must point to github.com")
    if provider == "gitlab" and host not in {"gitlab.com", "www.gitlab.com"}:
        raise ValueError("GitLab repository URL must point to gitlab.com")


def _strip_git_suffix(value: str) -> str:
    if value.endswith(".git"):
        return value[:-4]
    return value
