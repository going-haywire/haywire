"""GitLabProvider.

Blob URL: https://gitlab.com/{owner}/{repo}/-/blob/{ref}/{path}
Raw URL:  https://gitlab.com/{owner}/{repo}/-/raw/{ref}/{path}

GitLab supports nested subgroups, so `{owner}` may contain slashes
(e.g. `group/subgroup`). Repos themselves do not contain slashes.

**Host-parameterised.** gitlab.com is only the default. Self-hosted GitLab is
common — `gitlab.zhdk.ch`, `git.acme.example` — and each gets its own instance
so every pattern and every builder targets *that* host. Without this, declaring
a self-hosted host in ``~/.haywire/config.toml`` resolved to the shared
gitlab.com instance, which then emitted gitlab.com URLs for it: a link pointing
at the wrong server, which is worse than no link. That defect made
:func:`~haywire.core.marketstall.host_providers.config.load_self_hosted_hosts`
inert in practice.

Unlike GitHub, raw content lives on the same host under ``/-/raw/``, so there is
no second domain to parameterise.
"""

from __future__ import annotations

import re

from haywire.core.marketstall.host_providers.base import ParsedRef

DEFAULT_HOSTNAME = "gitlab.com"


class GitLabProvider:
    """Provider for gitlab.com, or for one self-hosted GitLab instance."""

    name = "gitlab"
    label = "GitLab"
    auth_docs = {
        "ssh": "https://docs.gitlab.com/user/ssh/",
        "https": "https://docs.gitlab.com/user/profile/personal_access_tokens/",
    }

    def __init__(self, hostname: str = DEFAULT_HOSTNAME) -> None:
        self._hostname = hostname
        host = re.escape(hostname)
        # Greedy owner (captures up to the last segment before /repo/-/blob/...).
        self._blob_pattern = re.compile(
            rf"^https://{host}/(?P<owner>.+)/(?P<repo>[^/]+)/-/blob/(?P<ref>[^/]+)/(?P<path>.+)$"
        )
        self._raw_pattern = re.compile(
            rf"^https://{host}/(?P<owner>.+)/(?P<repo>[^/]+)/-/raw/(?P<ref>[^/]+)/(?P<path>.+)$"
        )
        # A bare repository URL — no ref, no path. Owner is greedy for the same
        # reason as above: subgroups nest, and the repo is the last segment.
        self._origin_pattern = re.compile(rf"^https://{host}/(?P<owner>.+)/(?P<repo>[^/]+?)(?:\.git)?/?$")

    @property
    def hostname(self) -> str:
        """The host this instance serves. Never assume gitlab.com."""
        return self._hostname

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
        return f"https://{self._hostname}/{owner}/{repo}/-/raw/{ref}/{path}"

    def blob_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        return f"https://{self._hostname}/{owner}/{repo}/-/blob/{ref}/{path}"

    def tree_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        return f"https://{self._hostname}/{owner}/{repo}/-/tree/{ref}/{path}"

    def parse_origin(self, url: str) -> tuple[str, str] | None:
        m = self._origin_pattern.match(url.strip())
        return (m.group("owner"), m.group("repo")) if m else None
