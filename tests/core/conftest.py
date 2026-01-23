"""
Core module test fixtures.

Additional fixtures specific to core functionality testing.
"""

import pytest
from haywire.core.graph.base import BaseGraph


@pytest.fixture
def empty_graph() -> BaseGraph:
    """
    Provide an empty test graph for unit tests.
    
    This is a bare graph without library system loaded.
    Use for testing graph structure/API without nodes/edges.
    """
    return BaseGraph(
        graph_id='test_graph',
        name='Test Graph'
    )


@pytest.fixture
def graph_with_library_system(library_system) -> BaseGraph:
    """
    Provide a graph with full library system loaded.
    
    Use this for integration tests that need to create nodes/edges
    using NodeFactory and AdapterFactory.
    
    This fixture is marked with @pytest.mark.integration automatically
    since it depends on library_system.
    """
    return BaseGraph(
        graph_id='integration_test_graph',
        name='Integration Test Graph'
    )


@pytest.fixture
def sample_graph_with_nodes(
    empty_graph: BaseGraph,
    node_factory
):
    """
    Provide a graph with some test nodes.
    
    Note: Implementation depends on available test nodes.
    This is a placeholder that returns an empty graph.
    Override in specific test modules as needed.
    """
    return empty_graph
