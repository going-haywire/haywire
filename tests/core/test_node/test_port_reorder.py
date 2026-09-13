"""reorder_ports rewrites DataPort.order for one sibling group."""

from __future__ import annotations

import pytest

# Integration: building a node with real ports needs the library system, and
# reorder_ports() reaches self.wrapper — a bare instance has neither.
pytestmark = pytest.mark.integration


def _make_probe(graph, position=(100.0, 100.0)):
    from haybale_testing.nodes.testbed.reorder_probe import ReorderProbeNode

    wrapper = graph.create_node_wrapper(ReorderProbeNode.class_identity.registry_key, position=position)
    assert wrapper is not None, "node creation failed"
    return wrapper.node


def _inlet_ids(probe) -> list[str]:
    return [p.id for p in probe.get_visible_ports() if p.is_inlet()]


def test_reorder_assigns_new_order_values(graph_with_library_system) -> None:
    probe = _make_probe(graph_with_library_system)
    probe.reorder_ports(["c", "a", "b"])
    assert _inlet_ids(probe)[:3] == ["c", "a", "b"]


def test_reorder_leaves_other_lanes_alone(graph_with_library_system) -> None:
    probe = _make_probe(graph_with_library_system)
    before = probe.ports["out"].order
    probe.reorder_ports(["c", "b", "a"])
    assert probe.ports["out"].order == before


def test_reorder_ignores_unknown_ids(graph_with_library_system) -> None:
    """A stale id from a redrawn panel must not raise mid-gesture."""
    probe = _make_probe(graph_with_library_system)
    probe.reorder_ports(["c", "nope", "a", "b"])
    assert _inlet_ids(probe)[:3] == ["c", "a", "b"]


def test_reorder_is_a_noop_for_an_empty_list(graph_with_library_system) -> None:
    probe = _make_probe(graph_with_library_system)
    before = {p.id: p.order for p in probe.ports.values()}
    probe.reorder_ports([])
    assert {p.id: p.order for p in probe.ports.values()} == before


def test_order_survives_a_rejig(graph_with_library_system) -> None:
    """post_init runs rejig on every load; a re-added port must keep the user's order."""
    probe = _make_probe(graph_with_library_system)
    probe.reorder_ports(["dyn_c", "dyn_a", "dyn_b"])
    probe.rebuild()
    assert _inlet_ids(probe)[-3:] == ["dyn_c", "dyn_a", "dyn_b"]


def test_promotion_record_carries_order() -> None:
    from haywire.core.settings.settings import Promotion
    from haywire.core.types.enums import PortType

    record = Promotion(PortType.INLET)
    assert record.order is None
    assert record._replace(order=7).order == 7
