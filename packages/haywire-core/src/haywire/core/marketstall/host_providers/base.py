"""HostProvider Protocol + ParsedRef — spec §5.1.

No `parse_repo_url` and no `default_branch` — bare repo URLs are rejected
at input time (§4.2), so no provider ever needs to probe for a default branch.
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
    """One git host's URL conventions — spec §5.1."""

    name: str  # "github", "gitlab", etc.

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
