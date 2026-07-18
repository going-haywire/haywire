"""
Tests for StoreStrategy.should_store and the _is_set_by_node serialization gate.

Covers:
- The pure truth table of StoreStrategy.should_store across every flag and state
  (the OR semantics promised by the enum docstring — each flag only stores when
  its matching state holds, NEVER/NONE never store, ALWAYS always stores).
- The _is_set_by_node invariant: out() flags an outlet as node-set; an edge or a
  widget/programmatic inlet set clears it. Owned entirely by set_value().
"""

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.types.enums import StoreStrategy


@pytest.mark.unit
class TestShouldStore:
    """Pure truth table — no port needed."""

    def test_never_and_none_never_store(self):
        for ss in (StoreStrategy.NEVER, StoreStrategy.NONE):
            assert ss.should_store(is_linked=True, has_widget=True, node_set=True) is False, (
                f"{ss!r} must never store"
            )

    def test_always_always_stores(self):
        assert StoreStrategy.ALWAYS.should_store(is_linked=False, has_widget=False, node_set=False) is True

    def test_when_linked_only_stores_when_linked(self):
        ss = StoreStrategy.WHEN_LINKED
        assert ss.should_store(is_linked=True, has_widget=False, node_set=False) is True
        # The bug we fixed: this used to return True regardless of link state.
        assert ss.should_store(is_linked=False, has_widget=False, node_set=False) is False

    def test_has_widget_only_stores_with_widget(self):
        ss = StoreStrategy.HAS_WIDGET
        assert ss.should_store(is_linked=False, has_widget=True, node_set=False) is True
        # The bug we fixed: this used to return True even with no widget.
        assert ss.should_store(is_linked=False, has_widget=False, node_set=False) is False

    def test_node_set_only_stores_when_node_set(self):
        ss = StoreStrategy.NODE_SET
        assert ss.should_store(is_linked=False, has_widget=False, node_set=True) is True
        assert ss.should_store(is_linked=False, has_widget=False, node_set=False) is False

    def test_combined_flags_or_their_states(self):
        ss = StoreStrategy.HAS_WIDGET | StoreStrategy.NODE_SET
        # Either matching state stores; neither does not.
        assert ss.should_store(is_linked=False, has_widget=True, node_set=False) is True
        assert ss.should_store(is_linked=False, has_widget=False, node_set=True) is True
        assert ss.should_store(is_linked=False, has_widget=False, node_set=False) is False
        # WHEN_LINKED is not part of this combination, so being linked is irrelevant.
        assert ss.should_store(is_linked=True, has_widget=False, node_set=False) is False


@pytest.mark.integration
class TestStoreStrategyRoundTrip:
    """store_strategy must survive to_dict -> from_spec as a StoreStrategy enum.

    Regression: from_spec reconstructed flow_type/port_type/show_widget but not
    store_strategy, so a deserialized (or copied) port carried a plain int. The
    next serialize then crashed on `int.should_store(...)` (copy/paste of a node
    blew up with "'int' object has no attribute 'should_store'").
    """

    def test_store_strategy_survives_round_trip(self, graph_with_library_system: BaseGraph, library_system):
        import json

        from haywire.core.types.enums import StoreStrategy
        from haywire.core.types.port import DataPort

        node_a, _ = _create_two_nodes(graph_with_library_system)
        wrapper = node_a
        node = node_a.node
        # Pick any real port and give it a non-default, OR-combining strategy so a
        # round-trip that demoted it to int would change behaviour.
        port = next(iter(node.ports.values()))
        port.store_strategy = StoreStrategy.HAS_WIDGET | StoreStrategy.NODE_SET

        # Go through JSON, like a save/load or clipboard copy does. This is what
        # turns the IntFlag into a plain int and triggered the original crash.
        spec = json.loads(json.dumps(port.to_dict(include_data=True)))
        assert spec["kwargs"]["store_strategy"] == int(StoreStrategy.HAS_WIDGET | StoreStrategy.NODE_SET)
        assert type(spec["kwargs"]["store_strategy"]) is int

        rebuilt = DataPort.from_spec(spec, node._type_registry, wrapper, node)

        assert isinstance(rebuilt.store_strategy, StoreStrategy)
        assert rebuilt.store_strategy == StoreStrategy.HAS_WIDGET | StoreStrategy.NODE_SET
        # And the reconstructed port can serialize again without crashing — this
        # is the call that raised "'int' object has no attribute 'should_store'".
        rebuilt.to_dict(include_data=True)


def _create_two_nodes(graph: BaseGraph):
    from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

    key = EdgeLinkTestNode.class_identity.registry_key
    node_a = graph.create_node_wrapper(key, position=(100, 100))
    node_b = graph.create_node_wrapper(key, position=(300, 100))
    return node_a, node_b


@pytest.mark.integration
class TestIsSetByNodeInvariant:
    """set_value() owns _is_set_by_node; out() no longer flips it externally."""

    def test_out_flags_outlet_as_node_set(self, graph_with_library_system: BaseGraph, library_system):
        node_a, _ = _create_two_nodes(graph_with_library_system)
        outlet = node_a.node.ports["bool_outlet"]

        node_a.node.out("bool_outlet", True)
        assert outlet._is_set_by_node is True

    def test_widget_set_clears_node_set_on_inlet(self, graph_with_library_system: BaseGraph, library_system):
        node_a, _ = _create_two_nodes(graph_with_library_system)
        inlet = node_a.node.ports["bool_inlet"]

        # A programmatic/widget set (no edge_id) must not be flagged node-set.
        inlet.set_value(True)
        assert inlet._is_set_by_node is False

    def test_edge_driven_set_clears_node_set_on_inlet(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        node_a, _ = _create_two_nodes(graph_with_library_system)
        inlet = node_a.node.ports["bool_inlet"]

        inlet.set_value(True, edge_id="some-edge")
        assert inlet._is_set_by_node is False
