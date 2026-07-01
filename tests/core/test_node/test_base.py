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

        @node(label="Test Node")
        class TestNode(BaseNode):
            def init(self):
                pass

        assert hasattr(TestNode, "class_identity")
        assert TestNode.class_identity.registry_id == "TestNode"

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

    def test_cleanup_survives_throwing_on_teardown(
        self, graph_with_library_system: BaseGraph, integration_node_factory: NodeFactory
    ):
        """A subclass on_teardown() that raises must not block _cleanup().

        Regression: a node whose init() failed (e.g. a deserialized graph
        referencing a since-removed type key) never ran post_init(), so its
        on_teardown() can hit unset attributes and raise. Previously that
        exception propagated out of _cleanup() and aborted re-instantiation,
        wedging the node so a reset could never recover it.
        """
        available_nodes = integration_node_factory.list_all_nodes()
        if not available_nodes:
            pytest.skip("No nodes available in test libraries")

        wrapper = graph_with_library_system.create_node_wrapper(available_nodes[0], [0, 0])
        node_instance = wrapper.node

        def boom() -> None:
            raise AttributeError("simulated partial-init teardown failure")

        node_instance.on_teardown = boom  # type: ignore[method-assign]

        # Must not raise, and store cleanup must still run.
        node_instance._cleanup()
        assert len(node_instance._store) == 0
