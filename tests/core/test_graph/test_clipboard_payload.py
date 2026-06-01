# tests/core/test_graph/test_clipboard_payload.py
"""Unit tests for the pure clipboard-payload builder."""

import haywire.core.graph.editor  # noqa: F401 — import first (circular-import guard, see CLAUDE.md)

import pytest
from unittest.mock import MagicMock

from haywire.core.graph.clipboard import (
    build_clipboard_payload,
    is_haywire_payload,
    CLIPBOARD_FORMAT_VERSION,
)

pytestmark = pytest.mark.unit


def _fake_graph():
    """A graph with two nodes (n1, n2) and one edge n1->n2, plus a dangling edge n2->n3."""
    g = MagicMock()

    def node_wrapper(node_id):
        w = MagicMock()
        w.serialize.return_value = {
            "node_id": node_id,
            "registry_key": f"key.{node_id}",
            "position": [100.0 if node_id == "n1" else 300.0, 200.0],
            "node_data": {},
        }
        return w

    g.get_node_wrapper.side_effect = node_wrapper

    edge_in = MagicMock()
    edge_in.edge.to_dict.return_value = {
        "source_node_id": "n1",
        "outlet_port_id": "o",
        "sink_node_id": "n2",
        "inlet_port_id": "i",
        "edge_type": "data",
        "chain_adapter_keys": [],
        "is_lazy": False,
    }
    edge_out = MagicMock()
    edge_out.edge.to_dict.return_value = {
        "source_node_id": "n2",
        "outlet_port_id": "o",
        "sink_node_id": "n3",
        "inlet_port_id": "i",
        "edge_type": "data",
        "chain_adapter_keys": [],
        "is_lazy": False,
    }
    g.get_edge_wrapper.side_effect = lambda eid: {"e_in": edge_in, "e_out": edge_out}.get(eid)
    return g


def test_payload_has_discriminator_and_version():
    payload = build_clipboard_payload(_fake_graph(), ["n1", "n2"], ["e_in"], "sess123")
    assert payload["haywire_clipboard"] is True
    assert payload["format_version"] == CLIPBOARD_FORMAT_VERSION
    assert payload["source"]["session_id"] == "sess123"
    assert "timestamp" in payload["source"]


def test_payload_serializes_selected_nodes():
    payload = build_clipboard_payload(_fake_graph(), ["n1", "n2"], [], "s")
    assert set(payload["nodes"].keys()) == {"n1", "n2"}
    assert payload["nodes"]["n1"]["registry_key"] == "key.n1"


def test_both_endpoints_rule_drops_boundary_crossing_edges():
    # e_out (n2->n3) must be dropped because n3 is not in the selection.
    payload = build_clipboard_payload(_fake_graph(), ["n1", "n2"], ["e_in", "e_out"], "s")
    assert list(payload["edges"].keys()) == ["e_in"]


def test_bounding_box_spans_selected_node_positions():
    payload = build_clipboard_payload(_fake_graph(), ["n1", "n2"], [], "s")
    bb = payload["bounding_box"]
    assert bb == {"min_x": 100.0, "min_y": 200.0, "max_x": 300.0, "max_y": 200.0}


def test_empty_selection_yields_zero_bounding_box():
    payload = build_clipboard_payload(_fake_graph(), [], [], "s")
    assert payload["bounding_box"] == {"min_x": 0.0, "min_y": 0.0, "max_x": 0.0, "max_y": 0.0}
    assert payload["nodes"] == {}


def test_serialize_called_with_include_data_true():
    g = MagicMock()
    wrapper = MagicMock()
    wrapper.serialize.return_value = {
        "node_id": "n1",
        "registry_key": "key.n1",
        "position": [100.0, 200.0],
        "node_data": {},
    }
    g.get_node_wrapper.return_value = wrapper
    build_clipboard_payload(g, ["n1"], [], "s")
    wrapper.serialize.assert_called_once_with(include_data=True)


def test_is_haywire_payload_accepts_valid_rejects_other():
    payload = build_clipboard_payload(_fake_graph(), ["n1"], [], "s")
    assert is_haywire_payload(payload) is True
    assert is_haywire_payload({"foo": "bar"}) is False
    assert is_haywire_payload("plain text") is False
    assert is_haywire_payload({"haywire_clipboard": True, "format_version": 9999}) is False
    # missing source / timestamp -> rejected (paste arbitration needs it)
    assert is_haywire_payload({"haywire_clipboard": True, "format_version": 1}) is False
    assert is_haywire_payload({"haywire_clipboard": True, "format_version": 1, "source": {}}) is False
    assert (
        is_haywire_payload({"haywire_clipboard": True, "format_version": 1, "source": {"timestamp": "x"}})
        is False
    )
