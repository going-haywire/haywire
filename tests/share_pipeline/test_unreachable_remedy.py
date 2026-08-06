"""The unreachable-origin remedy links to the page that can actually help.

Two things are knowable at that point and both narrow the advice: the
transport (an SSH remote fails over keys, an HTTPS one over tokens) and the
host (``resolve_host`` honours ``[[hosts]]`` config, so a self-hosted GitLab
resolves to the GitLab provider). Getting either wrong sends the reader to a
page that cannot help them.
"""

from __future__ import annotations

import pytest

from haywire.core.publishing.pipeline.steps.preconditions import (
    SHARING_GUIDE_URL,
    _unreachable_failure,
)


def _unreachable_remedy(remote_url: str, hostname: str) -> str:
    """The failure's user-visible text, remedy plus link, as one string.

    The link travels on `doc_url` so the UI can render an anchor; these tests
    care only that the RIGHT url is chosen, so they flatten it back.
    """
    failure = _unreachable_failure(remote_url, hostname, "probe failed")
    return f"{failure.remedy}\n{failure.doc_label}: {failure.doc_url}"


pytestmark = pytest.mark.unit


def test_github_ssh_links_the_ssh_key_page() -> None:
    remedy = _unreachable_remedy("git@github.com:someone/repo.git", "github.com")

    assert "docs.github.com" in remedy
    assert "connecting-to-github-with-ssh" in remedy
    assert "SSH key" in remedy


def test_github_https_links_the_token_page_not_the_ssh_one() -> None:
    """The distinction is the whole point — a token problem is not a key problem."""
    remedy = _unreachable_remedy("https://github.com/someone/repo.git", "github.com")

    assert "personal-access-tokens" in remedy
    assert "connecting-to-github-with-ssh" not in remedy
    assert "credential helper" in remedy


def test_gitlab_ssh_and_https_link_different_pages() -> None:
    ssh = _unreachable_remedy("git@gitlab.com:someone/repo.git", "gitlab.com")
    https = _unreachable_remedy("https://gitlab.com/someone/repo.git", "gitlab.com")

    assert "docs.gitlab.com/user/ssh" in ssh
    assert "personal_access_tokens" in https
    assert ssh != https


def test_ssh_protocol_urls_are_recognized_as_ssh() -> None:
    """`ssh://git@host/owner/repo` is the same transport as the scp-like form."""
    remedy = _unreachable_remedy("ssh://git@github.com/someone/repo.git", "github.com")

    assert "connecting-to-github-with-ssh" in remedy


def test_an_unrecognized_host_falls_back_to_the_guide() -> None:
    """No link is invented from the hostname: a wrong URL looks authoritative."""
    remedy = _unreachable_remedy("git@git.example.org:someone/repo.git", "git.example.org")

    assert SHARING_GUIDE_URL in remedy
    assert "git.example.org/docs" not in remedy


def test_a_hostless_remote_falls_back_to_the_guide() -> None:
    """A filesystem remote (/srv/git/foo.git) names no host at all."""
    remedy = _unreachable_remedy("/srv/git/foo.git", "")

    assert SHARING_GUIDE_URL in remedy


def test_a_configured_self_hosted_host_gets_its_providers_docs(monkeypatch, tmp_path) -> None:
    """The payoff of routing through resolve_host: a [[hosts]] entry naming
    gitlab makes a self-hosted instance link GitLab's own docs."""
    config = tmp_path / "config.toml"
    config.write_text('[[hosts]]\nhostname = "git.acme.dev"\nprovider = "gitlab"\n')
    monkeypatch.setattr("haywire.core.marketstall.host_providers.config._user_config_path", lambda: config)

    remedy = _unreachable_remedy("git@git.acme.dev:someone/repo.git", "git.acme.dev")

    assert "docs.gitlab.com" in remedy
    assert SHARING_GUIDE_URL not in remedy


def test_the_link_label_uses_the_brands_own_capitalization() -> None:
    """`"github".title()` is "Github", which is not how the brand is written —
    so providers carry a `label` and the remedy uses it."""
    failure = _unreachable_failure("git@github.com:o/r.git", "github.com", "denied")
    assert "GitHub's" in failure.doc_label

    failure = _unreachable_failure("https://gitlab.com/o/r.git", "gitlab.com", "denied")
    assert "GitLab's" in failure.doc_label


def test_the_url_travels_as_data_not_inside_the_remedy_prose() -> None:
    """The UI renders `doc_url` as a real anchor; a URL buried in `remedy`
    would be dead text in that pre-wrapped label."""
    failure = _unreachable_failure("git@github.com:o/r.git", "github.com", "denied")

    assert failure.doc_url.startswith("https://")
    assert "http" not in failure.remedy
