"""ParsedRef sanity and Protocol shape tests."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_parsed_ref_construction() -> None:
    from haywire.core.marketstall.host_providers.base import ParsedRef

    p = ParsedRef(owner="alice", repo="cool-libs", ref="main", path="marketstall.toml")
    assert p.owner == "alice"
    assert p.repo == "cool-libs"
    assert p.ref == "main"
    assert p.path == "marketstall.toml"


@pytest.mark.unit
def test_parsed_ref_is_frozen() -> None:
    from haywire.core.marketstall.host_providers.base import ParsedRef

    p = ParsedRef(owner="a", repo="b", ref="main", path="x.toml")
    with pytest.raises((AttributeError, Exception)):
        p.owner = "other"  # type: ignore[misc]


@pytest.mark.unit
def test_github_matches_github_com() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = GitHubProvider()
    assert p.matches("github.com") is True
    assert p.matches("gitlab.com") is False
    assert p.matches("example.com") is False


@pytest.mark.unit
def test_github_parse_blob_url() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = GitHubProvider()
    parsed = p.parse_blob_url("https://github.com/alice/cool-libs/blob/main/marketstall.toml")
    assert parsed is not None
    assert parsed.owner == "alice"
    assert parsed.repo == "cool-libs"
    assert parsed.ref == "main"
    assert parsed.path == "marketstall.toml"


@pytest.mark.unit
def test_github_parse_blob_url_with_subpath() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = GitHubProvider()
    parsed = p.parse_blob_url("https://github.com/alice/cool-libs/blob/v0.2.0/stalls/haybale-foo.toml")
    assert parsed is not None
    assert parsed.ref == "v0.2.0"
    assert parsed.path == "stalls/haybale-foo.toml"


@pytest.mark.unit
def test_github_parse_blob_url_returns_none_for_non_github() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = GitHubProvider()
    assert p.parse_blob_url("https://gitlab.com/x/y/-/blob/main/file.toml") is None
    assert p.parse_blob_url("https://github.com/alice/cool-libs") is None  # no /blob/
    assert p.parse_blob_url("not a url") is None


@pytest.mark.unit
def test_github_parse_raw_url() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = GitHubProvider()
    parsed = p.parse_raw_url("https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml")
    assert parsed is not None
    assert parsed.owner == "alice"
    assert parsed.repo == "cool-libs"
    assert parsed.ref == "main"
    assert parsed.path == "marketstall.toml"


@pytest.mark.unit
def test_github_raw_url_construction() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = GitHubProvider()
    url = p.raw_url("alice", "cool-libs", "main", "marketstall.toml")
    assert url == "https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml"


@pytest.mark.unit
def test_github_blob_url_construction() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = GitHubProvider()
    url = p.blob_url("alice", "cool-libs", "main", "marketstall.toml")
    assert url == "https://github.com/alice/cool-libs/blob/main/marketstall.toml"


@pytest.mark.unit
def test_github_roundtrip_blob_to_raw_to_blob() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = GitHubProvider()
    original = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    parsed = p.parse_blob_url(original)
    assert parsed is not None
    raw = p.raw_url(parsed.owner, parsed.repo, parsed.ref, parsed.path)
    reparsed = p.parse_raw_url(raw)
    assert reparsed == parsed
    assert p.blob_url(reparsed.owner, reparsed.repo, reparsed.ref, reparsed.path) == original
