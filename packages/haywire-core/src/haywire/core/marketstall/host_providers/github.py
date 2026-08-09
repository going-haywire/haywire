"""GitHubProvider.

Blob URL: https://github.com/{owner}/{repo}/blob/{ref}/{path}
Raw URL:  https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}

`{ref}` can be a branch name, tag name, or commit SHA. The provider does not
distinguish — it carries whatever the author shared.

**Host-parameterised.** github.com is only the default. A self-hosted instance
(GitHub Enterprise) declared in ``~/.haywire/config.toml`` — or named by a
published ``origin_provider`` — gets its own instance, so every pattern and
every builder targets *that* host. A single shared github.com instance would
recognise the hostname and then emit github.com URLs for it, which is worse than
not matching at all.

Raw content is the one asymmetry: github.com serves it from the separate
``raw.githubusercontent.com`` domain, while Enterprise serves it from the same
host under ``/raw/``. :attr:`_raw_host` encodes that split.
"""

from __future__ import annotations

import re

from haywire.core.marketstall.host_providers.base import ParsedRef

DEFAULT_HOSTNAME = "github.com"
_DOTCOM_RAW_HOST = "raw.githubusercontent.com"


class GitHubProvider:
    """Provider for github.com, or for one GitHub Enterprise host."""

    name = "github"
    label = "GitHub"
    auth_docs = {
        "ssh": "https://docs.github.com/authentication/connecting-to-github-with-ssh",
        "https": "https://docs.github.com/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens",
    }

    def __init__(self, hostname: str = DEFAULT_HOSTNAME) -> None:
        self._hostname = hostname
        host = re.escape(hostname)
        self._blob_pattern = re.compile(
            rf"^https://{host}/(?P<owner>[^/]+)/(?P<repo>[^/]+)/blob/(?P<ref>[^/]+)/(?P<path>.+)$"
        )
        self._raw_pattern = re.compile(
            rf"^https://{re.escape(self._raw_host)}/(?P<owner>[^/]+)/(?P<repo>[^/]+)/"
            rf"{self._raw_infix}(?P<ref>[^/]+)/(?P<path>.+)$"
        )
        # A bare repository URL — no ref, no path. Optional trailing ".git"/"/".
        self._origin_pattern = re.compile(rf"^https://{host}/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$")

    @property
    def hostname(self) -> str:
        """The host this instance serves. Never assume github.com."""
        return self._hostname

    @property
    def _raw_host(self) -> str:
        """Where raw file content lives for this host.

        github.com serves it from a dedicated domain; Enterprise serves it from
        the instance itself.
        """
        return _DOTCOM_RAW_HOST if self._hostname == DEFAULT_HOSTNAME else self._hostname

    @property
    def _raw_infix(self) -> str:
        """The path segment before the ref in a raw URL — empty on github.com."""
        return "" if self._hostname == DEFAULT_HOSTNAME else "raw/"

    def matches(self, hostname: str) -> bool:
        return hostname == self._hostname

    def parse_blob_url(self, url: str) -> ParsedRef | None:
        m = self._blob_pattern.match(url)
        if m is None:
            return None
        return ParsedRef(
            owner=m.group("owner"),
            repo=m.group("repo"),
            ref=m.group("ref"),
            path=m.group("path"),
        )

    def parse_raw_url(self, url: str) -> ParsedRef | None:
        m = self._raw_pattern.match(url)
        if m is None:
            return None
        return ParsedRef(
            owner=m.group("owner"),
            repo=m.group("repo"),
            ref=m.group("ref"),
            path=m.group("path"),
        )

    def raw_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        return f"https://{self._raw_host}/{owner}/{repo}/{self._raw_infix}{ref}/{path}"

    def blob_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        return f"https://{self._hostname}/{owner}/{repo}/blob/{ref}/{path}"

    def tree_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        return f"https://{self._hostname}/{owner}/{repo}/tree/{ref}/{path}"

    def parse_origin(self, url: str) -> tuple[str, str] | None:
        m = self._origin_pattern.match(url.strip())
        return (m.group("owner"), m.group("repo")) if m else None
