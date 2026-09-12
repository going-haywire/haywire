"""Resolves the glyph a pin draws, across the port, the skin and the default."""

from __future__ import annotations

from typing import ClassVar

from haywire.core.types import CompoundType, DataPort, FlowType

from ..themes.icons import ICONS


class PinIconResolver:
    """Decides which glyph a pin draws.

    Three tiers, widest last: a glyph declared on the port or its type wins;
    otherwise this resolver's :attr:`ICONS` map answers by role; and any role
    the map omits degrades to its flow type, then to ``"fallback"``. A pin
    therefore always gets an icon — only a flow type that draws no pin at all
    resolves to ``None``.

    A skin reskins every pin in the graph by subclassing and replacing the map.
    Keys are optional: one entry is a complete resolver, because every role
    falls through to it.

    ```python
    class MinimalPinIcons(PinIconResolver):
        ICONS = {"fallback": "circle"}

    class ArrowPinIcons(PinIconResolver):
        ICONS = {"data_in": "chevron_right", "data": "arrow_right", "fallback": "circle"}
    ```

    Roles are ``<kind>_<direction>``, where *kind* is ``data``, ``compound``,
    ``control`` or ``callback``, and *direction* is ``in`` or ``out``. A pin
    accepting several links looks for a ``_multi`` suffix first, so
    ``data_in_multi`` styles a pooled inlet without touching single-link ones.

    Override :meth:`resolve` only to change the tier order itself; override
    :meth:`role_of` to key the map differently.

    Note that a type inherits its parent's icons: ``@type`` copies the parent
    identity wholesale, so a type derived from one that declares an icon keeps
    that glyph even across flow types. Pass ``icon_in=None`` (and
    ``icon_out=None``) on the derived type to drop it, the way ``widget_key``
    is cleared.
    """

    #: Glyph per role. A role absent here falls back to its flow type, then to
    #: ``"fallback"``, so a partial map is valid.
    ICONS: ClassVar[dict[str, str]] = {
        "data_in": ICONS.MY_LOCATION,
        "data_in_multi": ICONS.FIBER_SMART_RECORD,
        "data_out": ICONS.CIRCLE,
        "compound_in": ICONS.VIEW_DAY,
        "compound_in_multi": ICONS.WEB_STORIES,
        "compound_out": ICONS.VIEW_DAY,
        "control_in": ICONS.JOIN_LEFT,
        "control_out": ICONS.JOIN_RIGHT,
        "callback_in": ICONS.SWIPE_LEFT_ALT,
        "callback_out": ICONS.SWIPE_RIGHT_ALT,
        "fallback": ICONS.CIRCLE,
    }

    def resolve(self, pin: DataPort) -> str | None:
        """Return the glyph *pin* draws, or ``None`` if its flow type has no pin.

        The port answers first: ``icon_in``/``icon_out`` and their ``_multi``
        variants carry what the type declared, already resolved through
        ``DataTypeIdentity.__post_init__``, plus any per-port override.
        """
        kind = self._kind_of(pin)
        if kind is None:
            return None
        declared = self._declared(pin)
        return declared or self._from_map(kind, pin)

    def role_of(self, pin: DataPort) -> str:
        """Return the :attr:`ICONS` key for *pin*, e.g. ``"data_in_multi"``."""
        kind = self._kind_of(pin) or "data"
        return self._role(kind, pin)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _kind_of(self, pin: DataPort) -> str | None:
        """The map's *kind* segment for *pin*, or ``None`` for a pinless flow type."""
        flow = pin.flow_type
        if flow == FlowType.CONTROL:
            return "control"
        if flow == FlowType.CALLBACK:
            return "callback"
        if flow == FlowType.DATA:
            if pin.type_cls is not None and issubclass(pin.type_cls, CompoundType):
                return "compound"
            return "data"
        return None

    def _role(self, kind: str, pin: DataPort) -> str:
        direction = "in" if pin.is_inlet() else "out"
        suffix = "_multi" if pin.allow_multiple_links else ""
        return f"{kind}_{direction}{suffix}"

    def _declared(self, pin: DataPort) -> str | None:
        """The glyph the port or its type declared for this direction."""
        if pin.is_inlet():
            return (pin.icon_in_multi if pin.allow_multiple_links else pin.icon_in) or None
        return (pin.icon_out_multi if pin.allow_multiple_links else pin.icon_out) or None

    def _from_map(self, kind: str, pin: DataPort) -> str:
        """This resolver's glyph for *kind*, narrowest key first."""
        icons = self.ICONS
        direction = "in" if pin.is_inlet() else "out"
        keys = []
        if pin.allow_multiple_links:
            keys.append(f"{kind}_{direction}_multi")
        keys += [f"{kind}_{direction}", kind, "fallback"]
        for key in keys:
            icon = icons.get(key)
            if icon:
                return icon
        # A subclass replaced ICONS without a "fallback": the framework floor
        # keeps every pin drawable rather than rendering none.
        return PinIconResolver.ICONS["fallback"]


#: Shared default, used by any skin that does not supply its own.
DEFAULT_PIN_ICONS = PinIconResolver()
