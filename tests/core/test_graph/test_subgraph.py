"""SubgraphDefinition, the subgraphs table, GraphNode mirroring, and round-trip."""

from __future__ import annotations

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.node.node_wrapper import NodeWrapper


def _definition(graph: BaseGraph, key: str | None = None, label: str = "") -> SubgraphDefinition:
    key = key or graph.generate_unique_subgraph_key()
    definition = SubgraphDefinition(key=key, label=label, validation_scheduler=SyncScheduler())
    return graph.add_subgraph(definition)


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSubgraphTable:
    def test_a_fresh_graph_has_no_subgraphs(self, empty_graph: BaseGraph):
        assert empty_graph.subgraphs == {}
        assert empty_graph.get_subgraph("missing") is None

    def test_add_and_get_a_definition(self, empty_graph: BaseGraph):
        definition = _definition(empty_graph, key="sg_1", label="Filter")

        assert empty_graph.get_subgraph("sg_1") is definition
        assert definition.key == "sg_1"
        assert definition.label == "Filter"

    def test_a_definition_defaults_its_label_to_its_key(self, empty_graph: BaseGraph):
        assert _definition(empty_graph, key="sg_1").label == "sg_1"

    def test_a_duplicate_key_is_refused(self, empty_graph: BaseGraph):
        _definition(empty_graph, key="sg_1")
        with pytest.raises(ValueError, match="sg_1"):
            _definition(empty_graph, key="sg_1")

    def test_remove_drops_the_definition(self, empty_graph: BaseGraph):
        definition = _definition(empty_graph, key="sg_1")

        assert empty_graph.remove_subgraph("sg_1") is definition
        assert empty_graph.get_subgraph("sg_1") is None
        assert empty_graph.remove_subgraph("sg_1") is None

    def test_clear_drops_every_definition(self, empty_graph: BaseGraph):
        _definition(empty_graph, key="sg_1")
        _definition(empty_graph, key="sg_2")

        empty_graph.clear()

        assert empty_graph.subgraphs == {}

    def test_generated_keys_are_distinct(self, empty_graph: BaseGraph):
        keys = set()
        for _ in range(50):
            key = empty_graph.generate_unique_subgraph_key()
            _definition(empty_graph, key=key)
            keys.add(key)
        assert len(keys) == 50


# ---------------------------------------------------------------------------
# One id space across the tree
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRootUniqueIds:
    def test_a_root_graph_is_its_own_root(self, empty_graph: BaseGraph):
        assert empty_graph.root_graph is empty_graph

    def test_a_definition_resolves_the_host_as_its_root(self, empty_graph: BaseGraph):
        definition = _definition(empty_graph)
        assert definition.root_graph is empty_graph

    def test_nesting_resolves_to_the_outermost_graph(self, empty_graph: BaseGraph):
        outer = _definition(empty_graph, key="outer")
        inner = SubgraphDefinition(key="inner", validation_scheduler=SyncScheduler())
        outer.add_subgraph(inner)

        assert inner.root_graph is empty_graph

    def test_a_removed_definition_is_its_own_root_again(self, empty_graph: BaseGraph):
        definition = _definition(empty_graph, key="sg_1")
        empty_graph.remove_subgraph("sg_1")

        assert definition.root_graph is definition

    def test_the_tree_lookup_sees_through_nesting(self, empty_graph: BaseGraph):
        outer = _definition(empty_graph, key="outer")
        inner = SubgraphDefinition(key="inner", validation_scheduler=SyncScheduler())
        outer.add_subgraph(inner)

        empty_graph.node_wrappers["host_1"] = object()  # type: ignore[assignment]
        inner.node_wrappers["deep_1"] = object()  # type: ignore[assignment]

        assert empty_graph.tree_contains_node_id("host_1")
        assert empty_graph.tree_contains_node_id("deep_1")
        assert not empty_graph.tree_contains_node_id("nobody")

    def test_a_minted_id_avoids_one_taken_inside_a_subgraph(self, empty_graph: BaseGraph, monkeypatch):
        """The whole tree shares one id space, so an inner id must be skipped."""
        from haywire.core.library.utils import get_registry_id_from_key

        definition = _definition(empty_graph)
        prefix = get_registry_id_from_key("k")
        definition.node_wrappers[f"{prefix}_aaaaaa"] = object()  # type: ignore[assignment]

        suffixes = iter(["aaaaaa", "bbbbbb"])
        monkeypatch.setattr(
            "haywire.core.graph.base.uuid.uuid4",
            lambda: type("U", (), {"hex": next(suffixes)})(),
        )

        assert empty_graph.generate_unique_node_id("k") == f"{prefix}_bbbbbb"

    def test_a_definition_mints_against_the_whole_tree(self, empty_graph: BaseGraph, monkeypatch):
        from haywire.core.library.utils import get_registry_id_from_key

        definition = _definition(empty_graph)
        prefix = get_registry_id_from_key("k")
        empty_graph.node_wrappers[f"{prefix}_aaaaaa"] = object()  # type: ignore[assignment]

        suffixes = iter(["aaaaaa", "bbbbbb"])
        monkeypatch.setattr(
            "haywire.core.graph.base.uuid.uuid4",
            lambda: type("U", (), {"hex": next(suffixes)})(),
        )

        assert definition.generate_unique_node_id("k") == f"{prefix}_bbbbbb"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSubgraphSerialization:
    def test_to_dict_carries_the_table(self, empty_graph: BaseGraph):
        _definition(empty_graph, key="sg_1", label="Filter")

        data = empty_graph.to_dict()

        assert set(data["subgraphs"]) == {"sg_1"}
        assert data["subgraphs"]["sg_1"]["key"] == "sg_1"
        assert data["subgraphs"]["sg_1"]["label"] == "Filter"

    def test_an_empty_table_serializes_as_an_empty_dict(self, empty_graph: BaseGraph):
        assert empty_graph.to_dict()["subgraphs"] == {}

    def test_the_table_round_trips(self, empty_graph: BaseGraph):
        _definition(empty_graph, key="sg_1", label="Filter")
        _definition(empty_graph, key="sg_2", label="Blend")
        data = empty_graph.to_dict()

        restored = BaseGraph(filestem="restored", validation_scheduler=SyncScheduler())
        assert restored.load_from_dict(data) is True

        assert sorted(restored.subgraphs) == ["sg_1", "sg_2"]
        assert restored.get_subgraph("sg_1").label == "Filter"  # type: ignore[union-attr]
        assert restored.get_subgraph("sg_2").label == "Blend"  # type: ignore[union-attr]
        assert restored.get_subgraph("sg_1").root_graph is restored  # type: ignore[union-attr]

    def test_a_file_without_a_table_loads(self, empty_graph: BaseGraph):
        """A pre-feature graph restores nothing and keeps an empty table."""
        data = empty_graph.to_dict()
        del data["subgraphs"]

        restored = BaseGraph(filestem="restored", validation_scheduler=SyncScheduler())
        assert restored.load_from_dict(data) is True
        assert restored.subgraphs == {}

    def test_loading_twice_does_not_collide_on_keys(self, empty_graph: BaseGraph):
        """clear() drops the table, so a reload of the same file is not a duplicate."""
        _definition(empty_graph, key="sg_1")
        data = empty_graph.to_dict()

        restored = BaseGraph(filestem="restored", validation_scheduler=SyncScheduler())
        restored.load_from_dict(data)
        restored.load_from_dict(data)

        assert sorted(restored.subgraphs) == ["sg_1"]


# ---------------------------------------------------------------------------
# Contents, with real nodes
# ---------------------------------------------------------------------------


def _test_node(graph: BaseGraph) -> NodeWrapper:
    from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

    wrapper = graph.create_node_wrapper(EdgeLinkTestNode.class_identity.registry_key)
    assert wrapper is not None
    return wrapper


def _boundary(graph: BaseGraph, *, is_input: bool) -> NodeWrapper:
    from haywire.barn.builtin.nodes.subgraph_io import SubgraphInputNode, SubgraphOutputNode

    cls = SubgraphInputNode if is_input else SubgraphOutputNode
    wrapper = graph.create_node_wrapper(cls.class_identity.registry_key)
    assert wrapper is not None
    return wrapper


@pytest.mark.integration
class TestSubgraphContents:
    def test_boundary_node_accessors_find_the_pair(self, graph_with_library_system: BaseGraph):
        definition = _definition(graph_with_library_system)
        assert definition.input_node is None
        assert definition.output_node is None

        input_node = _boundary(definition, is_input=True)
        output_node = _boundary(definition, is_input=False)

        assert definition.input_node is input_node
        assert definition.output_node is output_node

    def test_content_nodes_exclude_the_boundary_pair(self, graph_with_library_system: BaseGraph):
        definition = _definition(graph_with_library_system)
        _boundary(definition, is_input=True)
        _boundary(definition, is_input=False)
        inner = _test_node(definition)

        assert [w.node_id for w in definition.content_node_wrappers()] == [inner.node_id]

    def test_inner_nodes_ids_are_unique_across_the_tree(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        definition = _definition(graph)

        host_ids = {_test_node(graph).node_id for _ in range(3)}
        inner_ids = {_test_node(definition).node_id for _ in range(3)}

        assert not host_ids & inner_ids

    def test_an_inner_node_resolves_its_graph_tier_from_the_subgraph(
        self, graph_with_library_system: BaseGraph
    ):
        """Decision 16: an inner node's graph() mirror reads its own Subgraph."""
        graph = graph_with_library_system
        definition = _definition(graph)
        inner = _test_node(definition)

        assert inner.graph is definition
        assert inner.node.wrapper.graph is definition
        # The tier the mirror resolves through is the definition's own bag.
        assert definition.settings_bag_for(type(definition.props)) is definition.props
        assert graph.settings_bag_for(type(graph.props)) is not definition.props

    def test_instantiate_mints_fresh_ids_and_rewires_edges(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        source = _test_node(graph)
        sink = _test_node(graph)
        edge = graph.create_edge_wrapper(source.node_id, "float_outlet", sink.node_id, "float_inlet")
        assert edge is not None

        template_nodes = {w.node_id: w.serialize() for w in (source, sink)}
        template_edges = {edge.edge_id: edge.edge.to_dict()}

        definition = _definition(graph)
        id_map = definition.instantiate(template_nodes, template_edges)

        assert set(id_map) == {source.node_id, sink.node_id}
        assert not set(id_map.values()) & set(graph.node_wrappers)
        assert len(definition.node_wrappers) == 2
        assert len(definition.edge_wrappers) == 1

        inner_edge = next(iter(definition.edge_wrappers.values()))
        assert inner_edge.source_node_id == id_map[source.node_id]
        assert inner_edge.sink_node_id == id_map[sink.node_id]

    def test_instantiating_twice_yields_disjoint_node_sets(self, graph_with_library_system: BaseGraph):
        """The keyed table keeps Abstraction reachable: minting never collides."""
        graph = graph_with_library_system
        template = {w.node_id: w.serialize() for w in [_test_node(graph)]}

        first = _definition(graph, key="sg_1")
        second = _definition(graph, key="sg_2")
        first_map = first.instantiate(template, {})
        second_map = second.instantiate(template, {})

        assert not set(first_map.values()) & set(second_map.values())
        assert not set(first.node_wrappers) & set(second.node_wrappers)

    def test_contents_round_trip_through_the_host(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        definition = _definition(graph, key="sg_1", label="Filter")
        _boundary(definition, is_input=True)
        _boundary(definition, is_input=False)
        inner = _test_node(definition)

        data = graph.to_dict()
        restored = BaseGraph(filestem="restored", validation_scheduler=SyncScheduler())
        assert restored.load_from_dict(data) is True

        restored_definition = restored.get_subgraph("sg_1")
        assert restored_definition is not None
        assert restored_definition.label == "Filter"
        assert set(restored_definition.node_wrappers) == set(definition.node_wrappers)
        assert restored_definition.get_node_wrapper(inner.node_id) is not None
        assert restored_definition.input_node is not None
        assert restored_definition.output_node is not None
