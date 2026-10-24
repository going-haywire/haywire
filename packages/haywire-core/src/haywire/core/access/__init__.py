"""Access vocabulary — the tier and level-mode enums and the resolver hook the studio fills in.

Core owns this because ``@panel(requires=...)`` / ``@editor(requires=...)`` /
``@farmhand(requires=...)`` are core decorators. Core deliberately knows nothing
about passwords, cookies, or ASGI — that lives in ``haywire_studio.auth``.
See ADR 0027.
"""

from haywire.core.access.level_mode import LevelMode, required_mode
from haywire.core.access.resolver import (
    AccessResolver,
    access_resolver,
    resolve_tier,
    set_access_resolver,
)
from haywire.core.access.tier import AccessTier, coerce_requirement, required_tier

__all__ = [
    "AccessResolver",
    "AccessTier",
    "LevelMode",
    "access_resolver",
    "coerce_requirement",
    "required_tier",
    "required_mode",
    "resolve_tier",
    "set_access_resolver",
]
