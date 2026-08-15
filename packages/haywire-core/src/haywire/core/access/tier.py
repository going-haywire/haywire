"""AccessTier — the three cumulative access levels (ADR 0027).

A StrEnum so the member *is* its wire string: it serializes into
``~/.haywire/auth.json`` and into ``@panel(access=...)`` declarations with no
conversion layer, exactly like ``SlotName`` does for slot names.

Cumulative: ``admin`` satisfies every check ``edit`` does, and ``edit``
satisfies every check ``view`` does. Ordering is expressed through
:meth:`satisfies` rather than by making this an IntEnum, so the wire values
stay strings and adding a tier later does not renumber anything.
"""

from __future__ import annotations

import logging
from enum import StrEnum

logger = logging.getLogger(__name__)


class AccessTier(StrEnum):
    """What a principal may reach. See ADR 0027 for what these do and do not guarantee."""

    VIEW = "view"
    EDIT = "edit"
    ADMIN = "admin"

    @property
    def rank(self) -> int:
        """Position in the cumulative order — higher includes lower."""
        return _RANKS[self]

    def satisfies(self, required: "AccessTier") -> bool:
        """True when holding this tier is enough to meet ``required``."""
        return self.rank >= required.rank


_RANKS: dict[AccessTier, int] = {
    AccessTier.VIEW: 0,
    AccessTier.EDIT: 1,
    AccessTier.ADMIN: 2,
}


def required_access(cls: type) -> AccessTier:
    """The tier a principal needs before ``cls`` may be shown or called.

    One definition for all three gated surfaces — panels, editors and Farmhand
    tools. Those surfaces enforce at different *points* (a panel is transient
    and filtered once; an editor binding is persisted and so is refused at
    admission as well), but they must not disagree about the *rule*.

    Falls back to VIEW — the most permissive tier — in three cases, all
    deliberate:

    * **No ``class_identity``.** A class caught mid-hot-reload, or a hand-built
      test double, would otherwise vanish from every surface at once. A missing
      identity is a framework hiccup, not a security assertion.
    * **An identity with no ``access`` field.** Node, skin, widget and theme
      identities have none by design (ADR 0027) — they are never gated, and
      asking this function about one must not raise.
    * **An ``access`` field that isn't a valid tier.** ``@panel(access=...)``
      takes the value as an untyped decorator kwarg, and identity dataclasses
      do no field validation — a typo like ``access="admni"`` must not become
      an ``AttributeError`` deep inside a gating check at render time.
    """
    identity = getattr(cls, "class_identity", None)
    declared = getattr(identity, "access", None)
    if declared is None:
        return AccessTier.VIEW
    try:
        # AccessTier is a StrEnum: AccessTier(AccessTier.ADMIN) is ADMIN
        # unchanged, and AccessTier("admin") coerces the wire string — so
        # this also normalizes a raw string that slipped past authoring time.
        return AccessTier(declared)
    except ValueError:
        logger.warning("Invalid access tier %r on %r; denying to VIEW", declared, cls)
        return AccessTier.VIEW
