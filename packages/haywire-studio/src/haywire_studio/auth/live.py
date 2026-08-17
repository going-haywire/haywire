"""Live document reads behind core's resolver hook (ADR 0027, ADR 0028).

The cookie carries identity; it never carries authority. So every
``ctx.can_edit()`` and every gate check asks the roster *now* rather than
trusting a tier stamped at login. That is what makes "remove a principal" an
actual revocation instead of a request — but it would be wasteful to re-parse
JSON on every call, so reads are cached against the file's mtime.

An ``os.stat`` per call is free; revocation still lands immediately because
saving the roster changes the mtime.
"""

from __future__ import annotations

import logging
from pathlib import Path

from haywire.core.access import AccessTier, set_access_resolver

from haywire_studio.security.document import load_document, security_path
from haywire_studio.security.errors import SecurityError
from haywire_studio.security.roster import Roster

logger = logging.getLogger(__name__)


class RosterCache:
    """Reads the roster, re-parsing only when the file's mtime/size changes.

    A read error keeps the last good roster (and logs) rather than degrading to
    an empty one: an empty roster means "authentication disabled", so treating a
    transient disk error as empty would open the door.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or security_path()
        self._stamp: tuple[float, int] | None = None
        self._roster: Roster = Roster()

    @property
    def path(self) -> Path:
        return self._path

    def roster(self) -> Roster:
        stamp = self._current_stamp()
        if stamp != self._stamp:
            try:
                self._roster = load_document(self._path).auth
                self._stamp = stamp
            except SecurityError:
                logger.warning(
                    "Security document at %s could not be read; keeping the last good roster",
                    self._path,
                )
        return self._roster

    def invalidate(self) -> None:
        """Force a re-parse on the next :meth:`roster` call.

        Used after this process itself writes the roster, so a write and a read
        inside the same mtime granularity cannot serve stale data.
        """
        self._stamp = None

    def _current_stamp(self) -> tuple[float, int] | None:
        try:
            info = self._path.stat()
        except OSError:
            return None
        return (info.st_mtime, info.st_size)


def install_resolver(cache: RosterCache) -> None:
    """Point core's ``resolve_tier`` at ``cache``.

    When the roster is disabled every principal resolves to ADMIN, which is what
    keeps an auth-off install behaving exactly as it did before. When enabled, an
    unknown principal resolves to VIEW rather than raising, so a stale cookie
    degrades to the least privilege instead of erroring inside a render.
    """

    def _resolve(name: str | None) -> AccessTier:
        roster = cache.roster()
        if not roster.enabled:
            return AccessTier.ADMIN
        if name is None:
            return AccessTier.VIEW
        principal = roster.find(name)
        return principal.tier if principal is not None else AccessTier.VIEW

    set_access_resolver(_resolve)
