"""Providers are bound to a host, not to github.com/gitlab.com.

This is the defect that made ``load_self_hosted_hosts()`` inert: declaring
``gitlab.zhdk.ch`` in ``~/.haywire/config.toml`` resolved to the *shared*
gitlab.com provider, which then built gitlab.com URLs for it — a link pointing
at a server that does not have the repository, which is worse than no link.
"""

import pytest

from haywire.core.marketstall.host_providers import (
    GitHubProvider,
    GitLabProvider,
    provider_for,
    resolve_host,
)

SELF_HOSTED = "gitlab.zhdk.ch"
ENTERPRISE = "github.acme.example"


@pytest.mark.unit
def test_self_hosted_gitlab_builds_urls_for_its_own_host() -> None:
    p = GitLabProvider(SELF_HOSTED)
    for url in (
        p.blob_url("haywire-libs", "haybale-superduper", "v0.0.1", "README.md"),
        p.raw_url("haywire-libs", "haybale-superduper", "v0.0.1", "README.md"),
        p.tree_url("haywire-libs", "haybale-superduper", "v0.0.1", "examples/"),
    ):
        assert url.startswith(f"https://{SELF_HOSTED}/")
        assert "gitlab.com" not in url


@pytest.mark.unit
def test_self_hosted_gitlab_matches_and_parses_only_its_own_host() -> None:
    p = GitLabProvider(SELF_HOSTED)
    assert p.matches(SELF_HOSTED)
    assert not p.matches("gitlab.com")
    assert p.parse_origin(f"https://{SELF_HOSTED}/haywire-libs/haybale-superduper") == (
        "haywire-libs",
        "haybale-superduper",
    )
    # A gitlab.com URL is not this instance's to parse.
    assert p.parse_origin("https://gitlab.com/group/repo") is None


@pytest.mark.unit
def test_defaults_are_unchanged() -> None:
    assert GitLabProvider().matches("gitlab.com")
    assert GitHubProvider().matches("github.com")
    assert GitHubProvider().raw_url("o", "r", "v1", "F.md").startswith("https://raw.githubusercontent.com/")


@pytest.mark.unit
def test_github_enterprise_serves_raw_from_its_own_host() -> None:
    """github.com serves raw from a separate domain; Enterprise does not."""
    p = GitHubProvider(ENTERPRISE)
    raw = p.raw_url("o", "r", "v1", "F.md")
    assert raw == f"https://{ENTERPRISE}/o/r/raw/v1/F.md"
    assert "raw.githubusercontent.com" not in raw


@pytest.mark.unit
def test_provider_for_binds_the_named_provider_to_a_host() -> None:
    p = provider_for("gitlab", SELF_HOSTED)
    assert p is not None
    assert p.blob_url("o", "r", "v1", "F.md").startswith(f"https://{SELF_HOSTED}/")
    assert provider_for("bitbucket", SELF_HOSTED) is None


@pytest.mark.unit
def test_resolve_host_binds_a_configured_host_to_itself(monkeypatch) -> None:
    """The bug in one assertion: resolve_host must not hand back gitlab.com."""
    monkeypatch.setattr(
        "haywire.core.marketstall.host_providers._host_config.load_self_hosted_hosts",
        lambda: {SELF_HOSTED: "gitlab"},
    )
    p = resolve_host(SELF_HOSTED)
    assert p is not None
    assert p.blob_url("o", "r", "v1", "F.md") == f"https://{SELF_HOSTED}/o/r/-/blob/v1/F.md"


@pytest.mark.unit
def test_unknown_host_still_resolves_to_none(monkeypatch) -> None:
    monkeypatch.setattr(
        "haywire.core.marketstall.host_providers._host_config.load_self_hosted_hosts",
        lambda: {},
    )
    assert resolve_host("git.unknown.example") is None
