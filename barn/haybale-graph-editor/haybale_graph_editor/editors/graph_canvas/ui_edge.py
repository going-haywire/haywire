"""
Edge visual state — how an EdgeWrapper's state becomes a drawn connection.

An edge has no UI object of its own. Unlike a node, which owns a NiceGUI
container and a rendered skin card (see UINode), an edge's entire visual
representation is the handful of stroke values in :class:`EdgeVisualState`,
serialised into a sync event and drawn imperatively by canvas.vue.

So there is no ``UIEdge`` class: there is a policy function
(:func:`edge_visual_state`) and a per-edge cache of its last result, held by
``VisualLayerHandlers.edge_states``. The cache is what lets a validation pass
emit only the edges that actually changed — ``on_validated`` runs the policy
for every edge that requires a redraw, and compares.

The policy stays in Python because it reads domain state the client never
sees: edge validity, wrapper warnings, and the length of the adapter chain.
canvas.vue receives only the resulting stroke values.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from haywire.core.edge.edge_wrapper import EdgeWrapper
from haywire.core.edge.style import DASH_PATTERNS, STYLE_FIELDS
from haywire.core.settings import settings_fields
from haywire.core.types import ArrowAt

logger = logging.getLogger(__name__)


@dataclass
class EdgeVisualState:
    """
    Visual state for connection rendering.

    This determines how the connection appears in the UI.
    All visual feedback is conveyed through these properties only.
    """

    edge_id: str

    # Visual properties
    stroke_color: str
    stroke_dasharray: str  # "" for solid, "5,5" for dashed, "2,4" for dotted
    opacity: float
    arrow_at: str  # ArrowAt value: the end a computed head is drawn at

    # State flags (used to derive visual properties)
    is_valid: bool
    has_warning: bool

    # A styled edge's declared width and heads, keyed as canvas.vue reads them:
    # "width", "arrowStart", "arrowEnd"; only the keys its style bag declares.
    style: dict[str, Any] = field(default_factory=dict)

    def __eq__(self, other) -> bool:
        """Compare visual states to detect changes.

        Deliberately ignores ``edge_id``: two states are equal when they would
        *draw* the same, which is the only question the redraw-dedupe in
        ``on_validated`` is asking. ``is_valid`` and ``has_warning`` take part
        because they pick the invalid colour and the warning glow; ``arrow_at``
        takes part because a rebuild can change the wire type; ``style`` takes
        part because a styled edge's width and heads are drawn from it.
        """
        if not isinstance(other, EdgeVisualState):
            return False
        return (
            self.stroke_color == other.stroke_color
            and self.stroke_dasharray == other.stroke_dasharray
            and self.opacity == other.opacity
            and self.arrow_at == other.arrow_at
            and self.is_valid == other.is_valid
            and self.has_warning == other.has_warning
            and self.style == other.style
        )


def calculate_dasharray(chain_length: int) -> str:
    """Dash pattern encoding how many adapters the edge's chain carries."""
    if chain_length == 0:
        return ""
    return "40,2" + ",2,2" * (chain_length)


def _declared_style(wrapper: EdgeWrapper) -> dict[str, Any]:
    """The recognised style fields the edge's bag declares, with their values; empty without a bag."""
    bag = wrapper.style
    if bag is None:
        return {}
    declared = settings_fields(bag)
    return {name: getattr(bag, name) for name in STYLE_FIELDS if name in declared}


def _canvas_style(style: dict[str, Any]) -> dict[str, Any]:
    """The width and heads of a declared style, keyed as canvas.vue reads them."""
    out: dict[str, Any] = {}
    if "width" in style:
        out["width"] = float(style["width"])
    if "arrow_start" in style:
        out["arrowStart"] = str(style["arrow_start"])
    if "arrow_end" in style:
        out["arrowEnd"] = str(style["arrow_end"])
    return out


def edge_visual_state(wrapper: EdgeWrapper) -> EdgeVisualState:
    """
    Calculate visual state from EdgeWrapper state.

    Visual States:
    1. VALID (default): Use gradient ('auto'), full opacity
    2. WARNING (chain changed): full opacity, drawn with the theme's warning colour by the canvas
    3. INVALID (error): dashed, reduced opacity, drawn in the theme's danger colour by the canvas

    A styled edge's declared colour replaces the gradient in the valid and
    warning states, and its declared dash replaces the chain dash in the valid
    state; its width and heads travel in ``style``. An invalid edge has no style
    bag, so it draws unstyled.

    Returns:
        EdgeVisualState with appropriate styling
    """
    wire = wrapper.wire_type
    arrow_at = wire.arrow_at.value if wire is not None else ArrowAt.INLET.value
    style = _declared_style(wrapper)
    color = str(style["color"]) if "color" in style else "auto"

    # State: INVALID (highest priority)
    if not wrapper.is_valid():
        return EdgeVisualState(
            edge_id=wrapper.edge_id,
            stroke_color="auto",  # The canvas paints an invalid edge with the --hw-danger token
            stroke_dasharray="5,5",  # Dashed
            opacity=0.7,
            arrow_at=arrow_at,
            is_valid=False,
            has_warning=False,
        )

    # State: WARNING (adapter chain changed)
    if wrapper.state.has_warning():
        return EdgeVisualState(
            edge_id=wrapper.edge_id,
            stroke_color=color,  # The canvas draws the warning glow with the --hw-warning token
            stroke_dasharray="2,2,2,2,2,5,5,5,5,5,5,5",
            opacity=1.0,
            arrow_at=arrow_at,
            is_valid=True,
            has_warning=True,
            style=_canvas_style(style),
        )

    # State: VALID (default) - 'auto' draws the gradient from the pins
    dash = DASH_PATTERNS.get(style["dash"]) if "dash" in style else None
    return EdgeVisualState(
        edge_id=wrapper.edge_id,
        stroke_color=color,
        stroke_dasharray=(
            dash if dash is not None else calculate_dasharray(len(wrapper.edge.chain_adapter_keys))
        ),
        opacity=1.0,
        arrow_at=arrow_at,
        is_valid=True,
        has_warning=False,
        style=_canvas_style(style),
    )


def edge_sync_payload(wrapper: EdgeWrapper, state: EdgeVisualState) -> dict:
    """One entry of a ``SyncAllEdgesEvent``'s ``edges`` list.

    Field names match ``SyncEdgeAdditionEvent``'s, because canvas.vue feeds
    each entry to the same ``_syncEdgeAddition`` handler — batching changes how
    many messages carry the edges, not what an edge looks like on the wire.
    """
    return {
        "edge_id": state.edge_id,
        "sourceNodeId": wrapper.source_node_id,
        "outletPinId": wrapper.outlet_port_id,
        "sinkNodeId": wrapper.sink_node_id,
        "inletPinId": wrapper.inlet_port_id,
        "outletPinFallback": wrapper.outletPinFallback,
        "inletPinFallback": wrapper.inletPinFallback,
        "isValid": state.is_valid,
        "hasWarning": state.has_warning,
        "strokeColor": state.stroke_color,
        "arrowAt": state.arrow_at,
        "strokeDasharray": state.stroke_dasharray,
        "opacity": state.opacity,
        "style": state.style,
    }
