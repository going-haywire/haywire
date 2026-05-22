"""~/.haywire/config.toml self-hosted host declarations — spec §5.4."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_load_self_hosted_returns_empty_when_file_missing(tmp_path: Path) -> None:
    from haywire.core.marketstall.host_providers.config import load_self_hosted_hosts

    config = tmp_path / "config.toml"
    assert load_self_hosted_hosts(config) == {}


@pytest.mark.unit
def test_load_self_hosted_parses_hosts_section(tmp_path: Path) -> None:
    from haywire.core.marketstall.host_providers.config import load_self_hosted_hosts

    config = tmp_path / "config.toml"
    config.write_text(
        "[[hosts]]\n"
        'hostname = "git.acme.example"\n'
        'provider = "gitlab"\n'
        "\n"
        "[[hosts]]\n"
        'hostname = "code.team.example"\n'
        'provider = "github"\n'
    )

    hosts = load_self_hosted_hosts(config)
    assert hosts == {
        "git.acme.example": "gitlab",
        "code.team.example": "github",
    }


@pytest.mark.unit
def test_load_self_hosted_ignores_unknown_provider(tmp_path: Path) -> None:
    """Entries naming a non-shipped provider are silently dropped."""
    from haywire.core.marketstall.host_providers.config import load_self_hosted_hosts

    config = tmp_path / "config.toml"
    config.write_text(
        '[[hosts]]\nhostname = "code.example"\nprovider = "gitea"\n'  # deferred — not in the first cut
    )

    assert load_self_hosted_hosts(config) == {}


@pytest.mark.unit
def test_resolve_host_consults_user_config_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A user-declared self-hosted hostname routes to the named built-in provider."""
    from haywire.core.marketstall.host_providers import resolve_host
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider
    from haywire.core.marketstall.host_providers import config as host_config_module

    config = tmp_path / "config.toml"
    config.write_text('[[hosts]]\nhostname = "git.acme.example"\nprovider = "gitlab"\n')
    monkeypatch.setattr(host_config_module, "_user_config_path", lambda: config)

    p = resolve_host("git.acme.example")
    assert isinstance(p, GitLabProvider)
