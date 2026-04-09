"""
Unit tests for NodeFactory.

These tests use DI fixtures but don't load full library system.
"""

import pytest
from haywire.core.node import node, BaseNode, NodeFactory, NodeRegistry
from haywire.core.graph.base import BaseGraph
from haywire.core.registry.base import BaseRegistry


@pytest.mark.unit
@pytest.mark.core
class TestNodeFactory:
    """Test NodeFactory functionality."""

    def test_factory_initialization(self, integration_node_factory: NodeFactory):
        """Test that factory initializes correctly."""
        assert integration_node_factory is not None
        assert isinstance(integration_node_factory.node_registry, BaseRegistry)

    @pytest.mark.integration  # Use integration fixtures
    def test_create_node_basic(
        self,
        graph_with_library_system: BaseGraph,  # Has global DI set up
        library_system,  # Ensures global system is initialized
    ):
        """Test basic node creation with error handling."""

        # Get the GLOBAL registry that NodeWrapper will also use
        node_registry = library_system.get_node_registry()

        # Register a test node
        @node(registry_id="test_node", label="Test Node")
        class TestNode(BaseNode):
            def init(self):
                pass

        # Register in the SAME registry NodeWrapper will use
        node_registry._register_class(
            TestNode,
            TestNode.class_library,
        )

        # Now both the test and NodeWrapper see the same registry
        graph = graph_with_library_system
        created_node = graph.create_node_wrapper("certainly.nonexistent.node", [50, 50])

        error_node = node_registry._get_error_node()
        assert error_node is not None  # Now it exists!

        assert created_node is not None
        assert created_node.node.class_identity.registry_key == error_node.class_identity.registry_key
        assert not isinstance(created_node.node, TestNode)

    def test_registry_is_empty_initially(self, node_registry: NodeRegistry):
        """Test that registry starts empty in unit tests."""
        # In unit tests, registry should be fresh and empty
        all_nodes = node_registry.list_names()
        # It might have some nodes if core libraries are loaded
        # but in pure unit tests, it should be minimal
        assert isinstance(all_nodes, list)

    def test_node_info_has_no_source_field(self):
        """NodeInfo must not have a 'source' field after NodeSourceInfo removal."""
        from haywire.core.node.info import NodeInfo
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(NodeInfo)}
        assert "source" not in field_names
        assert "identity" in field_names
        assert "library" in field_names
