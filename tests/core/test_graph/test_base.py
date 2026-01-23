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
        graph = BaseGraph(
            graph_id='test_graph',
            name='Test Graph'
        )
        
        assert graph.graph_id == 'test_graph'
        assert graph.name == 'Test Graph'
    
    def test_empty_graph_fixture(self, empty_graph: BaseGraph):
        """Test that empty_graph fixture works."""
        assert empty_graph is not None
        assert empty_graph.graph_id == 'test_graph'
        assert isinstance(empty_graph, BaseGraph)
    
    def test_graph_has_nodes_dict(self, empty_graph: BaseGraph):
        """Test that graph has nodes container."""
        # Implementation depends on BaseGraph structure
        # This is a placeholder test
        assert hasattr(empty_graph, 'node_wrappers') or hasattr(
            empty_graph,
            'get_node_wrapper'
        )
