"""GitLabProvider — spec §5.2 row 2."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_gitlab_matches_gitlab_com() -> None:
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    p = GitLabProvider()
    assert p.matches("gitlab.com") is True
    assert p.matches("github.com") is False


@pytest.mark.unit
def test_gitlab_parse_blob_url() -> None:
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    p = GitLabProvider()
    parsed = p.parse_blob_url("https://gitlab.com/alice/cool-libs/-/blob/main/marketstall.toml")
    assert parsed is not None
    assert parsed.owner == "alice"
    assert parsed.repo == "cool-libs"
    assert parsed.ref == "main"
    assert parsed.path == "marketstall.toml"


@pytest.mark.unit
def test_gitlab_parse_blob_url_with_subgroup() -> None:
    """GitLab supports nested groups. The 'owner' here is everything before /-/blob/."""
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    p = GitLabProvider()
    parsed = p.parse_blob_url("https://gitlab.com/group/subgroup/proj/-/blob/main/marketstall.toml")
    assert parsed is not None
    assert parsed.owner == "group/subgroup"
    assert parsed.repo == "proj"
    assert parsed.ref == "main"
    assert parsed.path == "marketstall.toml"


@pytest.mark.unit
def test_gitlab_parse_raw_url() -> None:
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    p = GitLabProvider()
    parsed = p.parse_raw_url("https://gitlab.com/alice/cool-libs/-/raw/main/marketstall.toml")
    assert parsed is not None
    assert parsed.owner == "alice"
    assert parsed.repo == "cool-libs"
    assert parsed.ref == "main"
    assert parsed.path == "marketstall.toml"


@pytest.mark.unit
def test_gitlab_raw_url_construction() -> None:
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    p = GitLabProvider()
    url = p.raw_url("alice", "cool-libs", "main", "marketstall.toml")
    assert url == "https://gitlab.com/alice/cool-libs/-/raw/main/marketstall.toml"


@pytest.mark.unit
def test_gitlab_blob_url_construction() -> None:
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    p = GitLabProvider()
    url = p.blob_url("alice", "cool-libs", "main", "marketstall.toml")
    assert url == "https://gitlab.com/alice/cool-libs/-/blob/main/marketstall.toml"


@pytest.mark.unit
def test_gitlab_does_not_parse_github_url() -> None:
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    p = GitLabProvider()
    assert p.parse_blob_url("https://github.com/alice/x/blob/main/file.toml") is None
    assert p.parse_raw_url("https://raw.githubusercontent.com/a/b/main/f.toml") is None


@pytest.mark.unit
def test_resolve_host_returns_github() -> None:
    from haywire.core.marketstall.host_providers import resolve_host
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = resolve_host("github.com")
    assert isinstance(p, GitHubProvider)


@pytest.mark.unit
def test_resolve_host_returns_gitlab() -> None:
    from haywire.core.marketstall.host_providers import resolve_host
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    p = resolve_host("gitlab.com")
    assert isinstance(p, GitLabProvider)


@pytest.mark.unit
def test_resolve_host_returns_none_for_unknown() -> None:
    from haywire.core.marketstall.host_providers import resolve_host

    assert resolve_host("bitbucket.org") is None
    assert resolve_host("example.com") is None
