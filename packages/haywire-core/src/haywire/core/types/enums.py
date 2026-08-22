from enum import Enum, IntFlag
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .port import DataPort


class FlowType(Enum):
    """
    Type of data flow through a port.

    - NONE: Configuration port (no flow, not a pin)
    - CONTROL: Execution flow (determines when nodes execute)
    - DATA: Data flow (passes values between nodes)
    - CALLBACK: Callback registration (event nodes declare interest)
    """

    CONTROL = "control"
    DATA = "data"
    CALLBACK = "callback"
    NONE = "none"


class PortType(Enum):
    """
    - INLET: Can receives data/control via Inlets
    - OUTLET: Sends data/control via Outlets
    - CONFIG: Has neither Inlets nor Outlets
    """

    UNDEFINED = "undefined"
    INLET = "inlet"
    OUTLET = "outlet"
    CONFIG = "config"


class LayoutDirection(Enum):
    """
    Orientation of flow across a node card.

    Purely presentational: the execution engine imposes no directionality on a
    graph, so this only decides which card edge a port's pin sits on and how a
    skin arranges its content. Resolved per node through the framework < graph
    < node chain (``node.props.layout_direction``), which means one graph may
    legitimately mix directions — nothing may assume both ends of an edge share
    an axis.

    - LEFT_TO_RIGHT: inlets left, outlets right (the historical default)
    - RIGHT_TO_LEFT: mirrored horizontally
    - TOP_TO_BOTTOM: inlets on the top edge, outlets on the bottom
    - BOTTOM_TO_TOP: mirrored vertically

    ``inlet_side``/``outlet_side`` and ``inlet_vector``/``outlet_vector`` are
    the single source for a pin's placement: the side doubles as the CSS
    property name used to offset the pin, and the vector is what the Vue edge
    layer reads from ``data-pin-dir-x``/``data-pin-dir-y``. Deriving both from
    here is what stops the two from silently disagreeing.
    """

    LEFT_TO_RIGHT = "l2r"
    RIGHT_TO_LEFT = "r2l"
    TOP_TO_BOTTOM = "t2b"
    BOTTOM_TO_TOP = "b2t"

    @property
    def label(self) -> str:
        """Human-readable name for settings widgets."""
        return _LAYOUT_DIRECTION_LABELS[self]

    @property
    def is_vertical(self) -> bool:
        """True when flow runs along the block axis (T2B / B2T)."""
        return self in (LayoutDirection.TOP_TO_BOTTOM, LayoutDirection.BOTTOM_TO_TOP)

    @property
    def glyph_transform(self) -> str:
        """CSS transform re-aiming a left/right-drawn pin glyph for this direction.

        Pin icons — the built-in CONTROL/CALLBACK glyphs and library authors'
        per-type ``icon_in``/``icon_out`` overrides alike — are all drawn
        pointing left/right. Transforming the element re-aims every one of them
        for free, including custom types this module has never heard of.

        All four values are centre-origin (a mirror or a quarter turn), so
        ``getBoundingClientRect()`` — which the edge layer reads — is unchanged.

        Empty string for L2R, which needs no transform.
        """
        return _LAYOUT_DIRECTION_GLYPH_TRANSFORMS[self]

    @property
    def inlet_side(self) -> str:
        """Card edge an inlet's pin sits on — also a CSS property name."""
        return _LAYOUT_DIRECTION_SIDES[self][0]

    @property
    def outlet_side(self) -> str:
        """Card edge an outlet's pin sits on — also a CSS property name."""
        return _LAYOUT_DIRECTION_SIDES[self][1]

    @property
    def inlet_vector(self) -> tuple[int, int]:
        """``(dir_x, dir_y)`` an inlet's edge leaves the card along."""
        return _LAYOUT_DIRECTION_VECTORS[self][0]

    @property
    def outlet_vector(self) -> tuple[int, int]:
        """``(dir_x, dir_y)`` an outlet's edge leaves the card along."""
        return _LAYOUT_DIRECTION_VECTORS[self][1]

    def side_for(self, port: "DataPort") -> str:
        """Card edge *port*'s pin sits on. Non-inlets are treated as outlets."""
        return self.inlet_side if port.is_inlet() else self.outlet_side

    def vector_for(self, port: "DataPort") -> tuple[int, int]:
        """Direction vector for *port*'s pin. Non-inlets are treated as outlets."""
        return self.inlet_vector if port.is_inlet() else self.outlet_vector

    @classmethod
    def coerce(cls, value: object) -> "LayoutDirection":
        """Resolve a stored value, falling back to L2R rather than raising.

        Settings store the enum's ``str`` value (CHOICES is a STRING subtype),
        and this runs on the render path — an unrecognised or stale string must
        degrade to today's layout, never take a node card down.
        """
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError:
            return cls.LEFT_TO_RIGHT


_LAYOUT_DIRECTION_LABELS: dict[LayoutDirection, str] = {
    LayoutDirection.LEFT_TO_RIGHT: "Left to right",
    LayoutDirection.RIGHT_TO_LEFT: "Right to left",
    LayoutDirection.TOP_TO_BOTTOM: "Top to bottom",
    LayoutDirection.BOTTOM_TO_TOP: "Bottom to top",
}

# (inlet, outlet) per direction. Sides are CSS property names; vectors point
# the way an edge leaves the card, and are mirrored between the two ends.
_LAYOUT_DIRECTION_SIDES: dict[LayoutDirection, tuple[str, str]] = {
    LayoutDirection.LEFT_TO_RIGHT: ("left", "right"),
    LayoutDirection.RIGHT_TO_LEFT: ("right", "left"),
    LayoutDirection.TOP_TO_BOTTOM: ("top", "bottom"),
    LayoutDirection.BOTTOM_TO_TOP: ("bottom", "top"),
}

_LAYOUT_DIRECTION_VECTORS: dict[LayoutDirection, tuple[tuple[int, int], tuple[int, int]]] = {
    LayoutDirection.LEFT_TO_RIGHT: ((-1, 0), (1, 0)),
    LayoutDirection.RIGHT_TO_LEFT: ((1, 0), (-1, 0)),
    LayoutDirection.TOP_TO_BOTTOM: ((0, -1), (0, 1)),
    LayoutDirection.BOTTOM_TO_TOP: ((0, 1), (0, -1)),
}

# Re-aiming transform for the left/right-drawn pin glyphs, per direction. Each
# is centre-origin so the pin's bounding box — the anchor the edge layer reads —
# does not move. R2L mirrors rather than turning: a 180deg rotation would also
# flip the glyph vertically, which reads wrong for asymmetric icons.
_LAYOUT_DIRECTION_GLYPH_TRANSFORMS: dict[LayoutDirection, str] = {
    LayoutDirection.LEFT_TO_RIGHT: "",
    LayoutDirection.RIGHT_TO_LEFT: "scaleX(-1)",
    LayoutDirection.TOP_TO_BOTTOM: "rotate(90deg)",
    LayoutDirection.BOTTOM_TO_TOP: "rotate(-90deg)",
}


class StoreStrategy(IntFlag):
    """
    Bitwise flags for when a port stores its value.

    - NEVER: do not store
    - HAS_WIDGET: store when the port has a widget
    - WHEN_LINKED: store when the port pin is linked
    - NODE_SET: store when the value was changed by the node
    - ALWAYS: store in any case

    Combine flags with OR; they trigger if any flag matches (there is no AND combination)::

        store_strategy = StoreStrategy.HAS_WIDGET | StoreStrategy.NODE_SET
    """

    NONE = 0
    NEVER = 1
    HAS_WIDGET = 2
    WHEN_LINKED = 4
    NODE_SET = 8
    ALWAYS = HAS_WIDGET | WHEN_LINKED | NODE_SET  # 14

    def should_store(self, *, is_linked: bool, has_widget: bool, node_set: bool) -> bool:
        """Resolve whether a port with this strategy should serialize its value.

        ``NEVER`` and ``NONE`` never store. ``ALWAYS`` always stores. Otherwise
        store if any set flag matches the port's current state (OR semantics —
        there is no AND combination).
        """
        if self & StoreStrategy.NEVER or self == StoreStrategy.NONE:
            return False
        if (self & StoreStrategy.ALWAYS) == StoreStrategy.ALWAYS:
            return True
        return bool(
            (self & StoreStrategy.WHEN_LINKED and is_linked)
            or (self & StoreStrategy.HAS_WIDGET and has_widget)
            or (self & StoreStrategy.NODE_SET and node_set)
        )


class ShowWidgetStrategy(Enum):
    """
    When a port's inline widget is rendered on the node card, relative to link state.

    The states are mutually exclusive — link state is a single boolean, so the
    widget shows in the linked state, the unlinked state, both, or neither. This
    is a plain ``Enum``, NOT an ``IntFlag`` like ``StoreStrategy``: visibility has
    no orthogonal dimension to combine (``ALWAYS`` already *is* linked-or-unlinked,
    ``NEVER`` is the empty case).

    - NEVER: widget never rendered on the node
    - NOT_LINKED: shown only when the pin is NOT linked (a connected inlet's
      widget is misleading — the upstream edge overrides it)
    - WHEN_LINKED: shown only when the pin IS linked
    - ALWAYS: always rendered

    Resolved by ``DataPort.should_show_widget()`` against ``is_linked()``.
    Direction defaults: inlet ``NOT_LINKED``, outlet ``NEVER``, config ``ALWAYS``.
    """

    NEVER = "never"
    NOT_LINKED = "not_linked"
    WHEN_LINKED = "when_linked"
    ALWAYS = "always"
