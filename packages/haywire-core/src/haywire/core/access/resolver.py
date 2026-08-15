"""The seam between core's access vocabulary and the studio's roster.

Core cannot read ``~/.haywire/auth.json`` — that is studio territory — but
``SessionContext.can_edit()`` has to answer *now*, from live authority, not
from something stamped onto the session at login (ADR 0027: "the cookie
carries identity; it never carries authority").

So the studio installs a resolver at startup and core calls it. With no
resolver installed — the default, and the state of every install that has not
enabled authentication — every principal resolves to ADMIN, so nothing
changes for existing users.

Module-level global rather than a ContextVar: see
``.insights/project_di_context.md`` — a ContextVar broke hot-reload because a
reload captured a different instance than the rest of the app. The DI context
made the same choice for the same reason.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from haywire.core.access.tier import AccessTier

logger = logging.getLogger(__name__)

AccessResolver = Callable[[Optional[str]], AccessTier]

_resolver: Optional[AccessResolver] = None


def set_access_resolver(fn: Optional[AccessResolver]) -> None:
    """Install (or with ``None``, remove) the tier resolver.

    Called once by the studio when authentication is enabled. Passing ``None``
    restores the unauthenticated default of ADMIN-for-everybody — which is also
    what tests should do in teardown.
    """
    global _resolver
    _resolver = fn


def access_resolver() -> Optional[AccessResolver]:
    """The currently installed resolver, or ``None``. Mainly for snapshot/restore in tests."""
    return _resolver


def resolve_tier(principal: Optional[str]) -> AccessTier:
    """The tier ``principal`` holds *right now*.

    Returns ADMIN when no resolver is installed (authentication disabled).
    Returns VIEW — the least privilege, not the most — when an installed
    resolver raises: a roster that cannot be read must not hand out admin.
    """
    resolver = _resolver
    if resolver is None:
        return AccessTier.ADMIN
    try:
        return resolver(principal)
    except Exception:
        logger.warning("Access resolver raised for principal %r; denying to VIEW", principal, exc_info=True)
        return AccessTier.VIEW
