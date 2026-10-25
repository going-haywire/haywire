"""
Unit tests for BaseGraph.

Tests graph creation and basic operations.
"""

import pytest
from haywire.core.graph.base import BaseGraph
from haywire.core.library.utils import get_registry_id_from_key


@pytest.mark.unit
@pytest.mark.core
class TestBaseGraph:
    """Test BaseGraph functionality."""

    def test_graph_creation(self):
        """Test basic graph creation."""
        graph = BaseGraph(filestem="Test Graph")

        assert graph.filestem == "Test Graph"
        assert graph.graph_id  # a uuid4 is minted, never supplied

    def test_graph_id_is_unique_per_instance(self):
        """Instance identity, not document identity: two graphs never share one."""
        assert BaseGraph(filestem="G").graph_id != BaseGraph(filestem="G").graph_id

    def test_empty_graph_fixture(self, empty_graph: BaseGraph):
        """Test that empty_graph fixture works."""
        assert empty_graph.graph_id

    def test_empty_graph_has_no_nodes(self, empty_graph: BaseGraph):
        """A freshly built graph starts with an empty node container."""
        assert empty_graph.node_wrappers == {}
        assert empty_graph.get_node_wrapper("missing") is None

    def test_generated_id_is_prefixed_by_registry_id(self, empty_graph: BaseGraph):
        """The id carries the node type, not the raw registry key."""
        node_id = empty_graph.generate_unique_node_id("mylib.math.Add")
        assert node_id.startswith(f"{get_registry_id_from_key('mylib.math.Add')}_")

    def test_generated_ids_are_distinct(self, empty_graph: BaseGraph):
        """Same registry key, many mints — the random suffix keeps them apart."""
        ids = {empty_graph.generate_unique_node_id("k") for _ in range(200)}
        assert len(ids) == 200

    def test_generated_id_retries_past_an_occupied_id(self, empty_graph: BaseGraph, monkeypatch):
        """The suffix is short (8 hex), so collisions are reachable: an id already
        in node_wrappers must be skipped rather than handed out twice."""
        suffixes = iter(["aaaaaaaa", "aaaaaaaa", "bbbbbbbb"])
        monkeypatch.setattr(
            "haywire.core.graph.base.uuid.uuid4",
            lambda: type("U", (), {"hex": next(suffixes)})(),
        )
        prefix = get_registry_id_from_key("k")
        empty_graph.node_wrappers[f"{prefix}_aaaaaaaa"] = object()  # type: ignore[assignment]

        assert empty_graph.generate_unique_node_id("k") == f"{prefix}_bbbbbbbb"

    @pytest.mark.parametrize("mint_in", ["host", "subgraph"])
    def test_generated_id_skips_an_id_used_elsewhere_in_the_tree(self, mint_in: str, monkeypatch):
        """Ids are unique across the Subgraph tree: a mint in either graph skips the other's ids."""
        from haywire.core.graph.subgraph import SubgraphDefinition

        host = BaseGraph(filestem="Host")
        definition = host.add_subgraph(SubgraphDefinition(key="sg"))
        prefix = get_registry_id_from_key("k")
        holder, minter = (definition, host) if mint_in == "host" else (host, definition)
        holder.node_wrappers[f"{prefix}_aaaaaaaa"] = object()  # type: ignore[assignment]
        suffixes = iter(["aaaaaaaa", "bbbbbbbb"])
        monkeypatch.setattr(
            "haywire.core.graph.base.uuid.uuid4",
            lambda: type("U", (), {"hex": next(suffixes)})(),
        )

        assert minter.generate_unique_node_id("k") == f"{prefix}_bbbbbbbb"
