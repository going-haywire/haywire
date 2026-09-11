"""The HostProvider Protocol and ParsedRef.

A provider never probes for a default branch: every URL it builds carries an
explicit ref, and a bare repo URL is rejected at input time.
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

    label: str
    """
    Human-facing brand for prose, in the brand's own capitalization
    (``"GitHub"``). Never derive it from ``name``: ``"github".title()`` gives
    ``"Github"``.
    """

    auth_docs: dict[str, str]
    """
    Where this host documents authenticating a push, keyed by transport:
    ``"ssh"`` for key setup, ``"https"`` for tokens and credential helpers.
    Either key may be absent, and the whole mapping may be empty; treat a
    missing key as "no link" rather than assuming both are present.
    """

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

        Takes a URL with no ref and no path, such as a row's ``origin``; a
        trailing ``.git`` or ``/`` is accepted.
        """
        ...
