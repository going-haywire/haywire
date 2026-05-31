"""Self-hosted host declarations from ~/.haywire/config.toml.

Example:
    [[hosts]]
    hostname = "git.acme.example"
    provider = "gitlab"

Only the shipped provider names ("github", "gitlab") are honored; unknown
providers are silently dropped (Bitbucket/Gitea will become honored once
their providers ship).
"""

from __future__ import annotations

from pathlib import Path

import toml

_SHIPPED_PROVIDERS = {"github", "gitlab"}


def _user_config_path() -> Path:
    """The canonical ~/.haywire/config.toml location. Wrapped for test monkeypatching."""
    return Path.home() / ".haywire" / "config.toml"


def load_self_hosted_hosts(config_path: Path | None = None) -> dict[str, str]:
    """Read [[hosts]] entries; return {hostname: provider_name}.

    Returns empty when the file does not exist or contains no valid entries.
    Drops entries naming providers that haven't shipped yet.
    """
    path = config_path if config_path is not None else _user_config_path()
    if not path.is_file():
        return {}
    try:
        data = toml.loads(path.read_text(encoding="utf-8"))
    except toml.TomlDecodeError:
        return {}

    out: dict[str, str] = {}
    for raw in data.get("hosts", []):
        hostname = raw.get("hostname")
        provider = raw.get("provider")
        if not isinstance(hostname, str) or not hostname:
            continue
        if not isinstance(provider, str) or provider not in _SHIPPED_PROVIDERS:
            continue
        out[hostname] = provider
    return out
