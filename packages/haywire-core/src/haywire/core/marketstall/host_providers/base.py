"""HostProvider Protocol + ParsedRef.

No `parse_repo_url` and no `default_branch` — bare repo URLs are rejected
at input time, so no provider ever needs to probe for a default branch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ParsedRef:
    """The four components of a host-specific blob/raw URL: owner, repo, ref, path."""

    owner: str
    repo: str
    ref: str
    path: str


class HostProvider(Protocol):
    """One git host's URL conventions."""

    name: str  # "github", "gitlab", etc. — the config/wire identifier.

    #: Human-facing brand, for prose. Distinct from ``name`` because
    #: ``"github".title()`` is ``"Github"``, which is not how the brand is
    #: written, and a UI that gets a brand's own capitalization wrong reads as
    #: careless.
    label: str

    #: Where this host documents authenticating a push, keyed by transport —
    #: an SSH remote fails over keys, an HTTPS one over tokens or a credential
    #: helper, and the two docs pages are different. Empty when the host has
    #: no page worth linking; callers must treat a missing key as "no link"
    #: rather than assume both are present.
    #:
    #: A plain mapping, not a method: this is a constant per host, and the
    #: rest of this Protocol is about parsing and building URLs. A provider
    #: that never adds one still satisfies the Protocol.
    auth_docs: dict[str, str]

    def matches(self, hostname: str) -> bool:
        """True if this provider handles URLs with this hostname."""
        ...

    def parse_blob_url(self, url: str) -> ParsedRef | None:
        """Parse a blob URL into ParsedRef. None if not a match."""
        ...

    def parse_raw_url(self, url: str) -> ParsedRef | None:
        """Parse a raw URL into ParsedRef. None if not a match."""
        ...

    def raw_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        """Construct the raw URL for fetching."""
        ...

    def blob_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        """Construct the share URL (canonical, browser-friendly)."""
        ...

    def tree_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        """Construct the browser URL for a *directory*.

        Distinct from :meth:`blob_url` because hosts route files and directories
        differently — GitHub uses /blob/ and /tree/, GitLab /-/blob/ and /-/tree/.
        """
        ...

    def parse_origin(self, url: str) -> tuple[str, str] | None:
        """Split a bare repository URL into ``(owner, repo)``. None if not a match.

        The existing parse_* methods take blob/raw URLs, which carry a ref and a
        path; a row's ``origin`` has neither, so it needs its own parser.
        """
        ...
