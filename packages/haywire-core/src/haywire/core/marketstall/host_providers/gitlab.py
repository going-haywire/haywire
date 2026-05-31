"""GitLabProvider.

Blob URL: https://gitlab.com/{owner}/{repo}/-/blob/{ref}/{path}
Raw URL:  https://gitlab.com/{owner}/{repo}/-/raw/{ref}/{path}

GitLab supports nested subgroups, so `{owner}` may contain slashes
(e.g. `group/subgroup`). Repos themselves do not contain slashes.
"""

from __future__ import annotations

import re

from haywire.core.marketstall.host_providers.base import ParsedRef

# Greedy owner (captures up to the last segment before /repo/-/blob/...).
_BLOB_PATTERN = re.compile(
    r"^https://gitlab\.com/(?P<owner>.+)/(?P<repo>[^/]+)/-/blob/(?P<ref>[^/]+)/(?P<path>.+)$"
)
_RAW_PATTERN = re.compile(
    r"^https://gitlab\.com/(?P<owner>.+)/(?P<repo>[^/]+)/-/raw/(?P<ref>[^/]+)/(?P<path>.+)$"
)


class GitLabProvider:
    """Built-in provider for gitlab.com."""

    name = "gitlab"

    def matches(self, hostname: str) -> bool:
        return hostname == "gitlab.com"

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
        return f"https://gitlab.com/{owner}/{repo}/-/raw/{ref}/{path}"

    def blob_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        return f"https://gitlab.com/{owner}/{repo}/-/blob/{ref}/{path}"
