"""A batched edge entry must carry exactly the keys canvas.vue destructures.

``SyncAllEdgesEvent`` ships a list of plain dicts, and canvas.vue's
``_syncAllEdges`` feeds each one straight to ``_syncEdgeAddition`` — the same
handler a single ``SyncEdgeAdditionEvent`` lands in. So the batch entries are
that event's field set, by value rather than by type: nothing on either side
checks the correspondence at runtime.

Which makes every way of breaking it silent. Rename a field on
``SyncEdgeAdditionEvent`` and the dataclass still constructs, the batch still
sends, the websocket frame still arrives — and canvas.vue destructures
``undefined``, so the edges just do not appear. No exception, no console error,
nothing in the Python log.

Only the wire contract is asserted here. The other half — that
``edge_sync_payload`` reads attributes that exist on ``EdgeWrapper`` — is
already covered by mypy, since the parameter is typed.
"""

from dataclasses import fields
from types import SimpleNamespace
from typing import cast

from haybale_graph_editor.editors.graph_canvas.ui_edge import (
    EdgeVisualState,
    edge_sync_payload,
)
from haywire.core.edge.edge_wrapper import EdgeWrapper
from haywire.ui.components.graph.event_definitions import SyncEdgeAdditionEvent


def _wrapper() -> EdgeWrapper:
    """Stand-in carrying just the EdgeWrapper attributes the payload reads.

    Cast rather than constructed: a real EdgeWrapper needs a real graph with
    two real nodes, which would move this into the integration tier to assert
    something that has nothing to do with graphs. The cast is not a hole in the
    wrapper-side coverage — mypy still checks ``edge_sync_payload``'s body
    against the real ``EdgeWrapper``, so an attribute renamed there is caught
    at the definition, not here.
    """
    return cast(
        EdgeWrapper,
        SimpleNamespace(
            source_node_id="node_a",
            outlet_port_id="float_outlet_0",
            sink_node_id="node_b",
            inlet_port_id="float_inlet_0",
            outletPinFallback="float_outlet_0>>root_out",
            inletPinFallback="float_inlet_0>>root_in",
        ),
    )


def _state() -> EdgeVisualState:
    return EdgeVisualState(
        edge_id="node_a[float_outlet_0]->node_b[float_inlet_0]",
        stroke_color="auto",
        stroke_width=2,
        stroke_dasharray="",
        opacity=1.0,
        is_valid=True,
        has_warning=False,
    )


def test_batch_entry_keys_match_the_single_edge_event_fields():
    """The batch entry and SyncEdgeAdditionEvent must stay one shape.

    Equality both ways on purpose: a missing key leaves canvas.vue
    destructuring undefined, and an extra one is a value Python believes it
    sends that nothing on the client reads.
    """
    payload_keys = set(edge_sync_payload(_wrapper(), _state()).keys())
    event_keys = {f.name for f in fields(SyncEdgeAdditionEvent)}

    assert payload_keys == event_keys, (
        "A batched edge entry no longer matches SyncEdgeAdditionEvent's fields.\n"
        f"  missing from the batch entry: {sorted(event_keys - payload_keys)}\n"
        f"  sent but not a field:         {sorted(payload_keys - event_keys)}\n"
        "canvas.vue's _syncAllEdges feeds each entry to _syncEdgeAddition, which "
        "destructures these names — a mismatch makes edges silently fail to draw, "
        "with no error on either side. Update edge_sync_payload() to match."
    )


def test_batch_entry_carries_the_wrapper_and_state_values():
    """Guards a key set that matches while the values behind it are wrong."""
    payload = edge_sync_payload(_wrapper(), _state())

    assert payload["sourceNodeId"] == "node_a"
    assert payload["outletPinId"] == "float_outlet_0"
    assert payload["sinkNodeId"] == "node_b"
    assert payload["inletPinId"] == "float_inlet_0"
    assert payload["outletPinFallback"] == "float_outlet_0>>root_out"
    assert payload["inletPinFallback"] == "float_inlet_0>>root_in"
    assert payload["edge_id"] == "node_a[float_outlet_0]->node_b[float_inlet_0]"
    assert payload["strokeColor"] == "auto"
    assert payload["strokeWidth"] == 2
    assert payload["strokeDasharray"] == ""
    assert payload["opacity"] == 1.0
    assert payload["isValid"] is True
    assert payload["hasWarning"] is False
