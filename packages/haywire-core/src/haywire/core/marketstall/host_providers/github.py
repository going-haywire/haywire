"""GitHubProvider.

Blob URL: https://github.com/{owner}/{repo}/blob/{ref}/{path}
Raw URL:  https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}

`{ref}` can be a branch name, tag name, or commit SHA. The provider does not
distinguish — it carries whatever the author shared.
"""

from __future__ import annotations

import re

from haywire.core.marketstall.host_providers.base import ParsedRef

_BLOB_PATTERN = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/blob/(?P<ref>[^/]+)/(?P<path>.+)$"
)
_RAW_PATTERN = re.compile(
    r"^https://raw\.githubusercontent\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/(?P<ref>[^/]+)/(?P<path>.+)$"
)
# A bare repository URL — no ref, no path. Optional trailing ".git"/"/".
_ORIGIN_PATTERN = re.compile(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$")


class GitHubProvider:
    """Built-in provider for github.com (and matched self-hosted aliases via config)."""

    name = "github"
    label = "GitHub"
    auth_docs = {
        "ssh": "https://docs.github.com/authentication/connecting-to-github-with-ssh",
        "https": "https://docs.github.com/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens",
    }

    def matches(self, hostname: str) -> bool:
        return hostname == "github.com"

    def parse_blob_url(self, url: str) -> ParsedRef | None:
        m = _BLOB_PATTERN.match(url)
        if m is None:
            return None
        return ParsedRef(
            owner=m.group("owner"),
            repo=m.group("repo"),
            ref=m.group("ref"),
            path=m.group("path"),
        )

    def parse_raw_url(self, url: str) -> ParsedRef | None:
        m = _RAW_PATTERN.match(url)
        if m is None:
            return None
        return ParsedRef(
            owner=m.group("owner"),
            repo=m.group("repo"),
            ref=m.group("ref"),
            path=m.group("path"),
        )

    def raw_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"

    def blob_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        return f"https://github.com/{owner}/{repo}/blob/{ref}/{path}"

    def tree_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        return f"https://github.com/{owner}/{repo}/tree/{ref}/{path}"

    def parse_origin(self, url: str) -> tuple[str, str] | None:
        m = _ORIGIN_PATTERN.match(url.strip())
        return (m.group("owner"), m.group("repo")) if m else None
