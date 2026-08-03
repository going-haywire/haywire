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
        graph = BaseGraph(graph_id="test_graph", name="Test Graph")

        assert graph.graph_id == "test_graph"
        assert graph.name == "Test Graph"

    def test_empty_graph_fixture(self, empty_graph: BaseGraph):
        """Test that empty_graph fixture works."""
        assert empty_graph.graph_id == "test_graph"

    def test_empty_graph_has_no_nodes(self, empty_graph: BaseGraph):
        """A freshly built graph starts with an empty node container."""
        assert empty_graph.node_wrappers == {}
        assert empty_graph.get_node_wrapper("missing") is None
