"""
Unit tests for BaseNode.

Tests the core node functionality.
"""

import pytest
from haywire.core.node import node, BaseNode, NodeFactory
from haywire.core.graph.base import BaseGraph


@pytest.mark.unit
@pytest.mark.core
class TestBaseNode:
    """Test BaseNode functionality."""

    def test_node_has_registry_key(self):
        """Test that decorated nodes get registry key."""

        @node(registry_id="test_node", label="Test Node")
        class TestNode(BaseNode):
            def init(self):
                pass

        assert hasattr(TestNode, "class_identity")
        assert TestNode.class_identity.registry_id == "test_node"

    def test_node_metadata(self):
        """Test that node metadata is properly set."""

        @node(
            registry_id="metadata_test",
            label="Metadata Test Node",
            description="A test node",
            search_tags=["test", "example"],
        )
        class MetadataNode(BaseNode):
            def init(self):
                pass

        assert MetadataNode.class_identity.registry_id == "metadata_test"
        # Note: Full metadata testing depends on implementation


@pytest.mark.integration
@pytest.mark.core
class TestBaseNodeWithLibraries:
    """Test BaseNode with full library system loaded."""

    def test_create_node_from_library(
        self, graph_with_library_system: BaseGraph, integration_node_factory: NodeFactory
    ):
        """
        Example: Test creating actual nodes from libraries.

        This shows how to use graph_with_library_system fixture
        for integration tests that need NodeFactory.
        """
        graph = graph_with_library_system

        # Get available nodes from the loaded libraries
        available_nodes = integration_node_factory.list_all_nodes()

        if available_nodes:
            # Try to create the first available node
            first_node_key = available_nodes[0]

            nodeWrapper = graph.create_node_wrapper(first_node_key, [100, 100])

            assert nodeWrapper is not None
            assert nodeWrapper.node.class_identity.registry_key == first_node_key
        else:
            pytest.skip("No nodes available in test libraries")
