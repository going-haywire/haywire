"""GitHubProvider — spec §5.2 row 1.

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


class GitHubProvider:
    """Built-in provider for github.com (and matched self-hosted aliases via config)."""

    name = "github"

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
