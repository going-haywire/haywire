"""AccessTier — the four cumulative access levels (ADR 0027).

A StrEnum so the member *is* its wire string: it serializes into
``~/.haywire/auth.json`` and into ``@panel(requires=...)`` declarations with no
conversion layer, exactly like ``SlotName`` does for slot names.

Cumulative: ``admin`` satisfies every check ``edit`` does, ``edit`` every
check ``operate`` does, and ``operate`` every check ``view`` does. Ordering is
expressed through :meth:`satisfies`, so the wire values stay strings.
"""

from __future__ import annotations

import logging
from enum import StrEnum

logger = logging.getLogger(__name__)


class AccessTier(StrEnum):
    """What a principal may reach. See ADR 0027 for what these do and do not guarantee."""

    VIEW = "view"
    OPERATE = "operate"
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
    AccessTier.OPERATE: 1,
    AccessTier.EDIT: 2,
    AccessTier.ADMIN: 3,
}


def coerce_requirement(value: object) -> AccessTier:
    """Strictly coerce a decorator's ``requires=`` tier to an :class:`AccessTier`.

    An ``AccessTier`` passes through; a plain ``str`` is read as a tier name
    (``ValueError`` when unknown). Anything else raises ``TypeError`` — notably a
    ``LevelMode``, which is a ``StrEnum`` too and would otherwise be accepted
    silently as its wire string.
    """
    if isinstance(value, AccessTier):
        return value
    if type(value) is str:
        return AccessTier(value)
    raise TypeError(f"requires= must be an AccessTier or a tier name, got {value!r}")


def required_tier(cls: type) -> AccessTier:
    """The tier a principal needs before ``cls`` may be shown or called.

    One definition for all three gated surfaces — panels, editors and Farmhand
    tools. Those surfaces enforce at different *points* (a panel is transient
    and filtered once; an editor binding is persisted and so is refused at
    admission as well), but they must not disagree about the *rule*.

    Falls back to ``EDIT``, the default of every access requirement, in three
    cases:

    * **No ``class_identity``**, as on a hand-built test double or a class
      caught mid-hot-reload.
    * **An identity with no ``requires`` field.** Node, skin, widget and theme
      identities have none (ADR 0027); asking about one does not raise.
    * **A ``requires`` value that is not a tier name**, on a hand-built
      identity (the decorators reject one with :func:`coerce_requirement`).
      It is logged.
    """
    identity = getattr(cls, "class_identity", None)
    declared = getattr(identity, "requires", None)
    if declared is None:
        return AccessTier.EDIT
    try:
        # AccessTier is a StrEnum: AccessTier(AccessTier.ADMIN) is ADMIN
        # unchanged, and AccessTier("admin") coerces the wire string — so
        # this also normalizes a raw string that slipped past authoring time.
        return AccessTier(declared)
    except ValueError:
        logger.warning("Invalid access requirement %r on %r; requiring EDIT", declared, cls)
        return AccessTier.EDIT
