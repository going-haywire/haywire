"""
Unit tests for BaseGraph.

Tests graph creation and basic operations.
"""

import pytest
from haywire.core.graph.base import BaseGraph


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
