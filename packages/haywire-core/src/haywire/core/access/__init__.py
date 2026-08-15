"""Access vocabulary — the tier enum and the resolver hook the studio fills in.

Core owns this because ``@panel(access=...)`` / ``@editor(access=...)`` /
``@farmhand(access=...)`` are core decorators. Core deliberately knows nothing
about passwords, cookies, or ASGI — that lives in ``haywire_studio.auth``.
See ADR 0027.
"""

from haywire.core.access.resolver import (
    AccessResolver,
    access_resolver,
    resolve_tier,
    set_access_resolver,
)
from haywire.core.access.tier import AccessTier, required_access

__all__ = [
    "AccessResolver",
    "AccessTier",
    "access_resolver",
    "required_access",
    "resolve_tier",
    "set_access_resolver",
]
