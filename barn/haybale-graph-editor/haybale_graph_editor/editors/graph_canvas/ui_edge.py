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
from dataclasses import dataclass

from haywire.core.edge.edge_wrapper import EdgeWrapper

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
    stroke_width: int
    stroke_dasharray: str  # "" for solid, "5,5" for dashed, "2,4" for dotted
    opacity: float

    # State flags (used to derive visual properties)
    is_valid: bool
    has_warning: bool

    def __eq__(self, other) -> bool:
        """Compare visual states to detect changes.

        Deliberately ignores ``edge_id`` and the state flags: two states are
        equal when they would *draw* the same, which is the only question the
        redraw-dedupe in ``on_validated`` is asking.
        """
        if not isinstance(other, EdgeVisualState):
            return False
        return (
            self.stroke_color == other.stroke_color
            and self.stroke_width == other.stroke_width
            and self.stroke_dasharray == other.stroke_dasharray
            and self.opacity == other.opacity
        )


def calculate_dasharray(chain_length: int) -> str:
    """Dash pattern encoding how many adapters the edge's chain carries."""
    if chain_length == 0:
        return ""
    return "40,2" + ",2,2" * (chain_length)


def edge_visual_state(wrapper: EdgeWrapper) -> EdgeVisualState:
    """
    Calculate visual state from EdgeWrapper state.

    Visual States:
    1. VALID (default): Use gradient ('auto'), full opacity
    2. WARNING (chain changed): Orange color, full opacity
    3. INVALID (error): Red dashed line, reduced opacity

    Returns:
        EdgeVisualState with appropriate styling
    """
    # State: INVALID (highest priority)
    if not wrapper.is_valid():
        return EdgeVisualState(
            edge_id=wrapper.edge_id,
            stroke_color="#EF4444",  # Red
            stroke_width=2,
            stroke_dasharray="5,5",  # Dashed
            opacity=0.7,
            is_valid=False,
            has_warning=False,
        )

    # State: WARNING (adapter chain changed)
    if wrapper.state.has_warning():
        return EdgeVisualState(
            edge_id=wrapper.edge_id,
            stroke_color="auto",  # Orange/Amber
            stroke_width=2,
            stroke_dasharray="2,2,2,2,2,5,5,5,5,5,5,5",  # Solid
            opacity=1.0,
            is_valid=True,
            has_warning=True,
        )

    # State: VALID (default) - use 'auto' for gradient
    return EdgeVisualState(
        edge_id=wrapper.edge_id,
        stroke_color="auto",  # Use gradient from pins
        stroke_width=2,
        stroke_dasharray=calculate_dasharray(len(wrapper.edge.chain_adapter_keys)),  # Solid
        opacity=1.0,
        is_valid=True,
        has_warning=False,
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
        "strokeWidth": state.stroke_width,
        "strokeDasharray": state.stroke_dasharray,
        "opacity": state.opacity,
    }
