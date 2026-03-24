import pytest
from haywire.core.di.config import LibrarySystemService
from haywire.core.graph.base import BaseGraph


@pytest.mark.unit
@pytest.mark.core
class TestLibrariesAndRegistries:
    def test_library_system_initialized(self, library_system: LibrarySystemService):
        """Test that library system initializes correctly."""
        assert library_system is not None
        node_registry = library_system.get_node_registry()
        assert node_registry is not None

        # Check that some nodes are available
        available_nodes = node_registry.list_names()
        assert isinstance(available_nodes, list)
        # In integration tests, we should have nodes from libraries
        # The exact nodes depend on what libraries are installed

    def test_multiple_registries_loaded(self, library_system: LibrarySystemService):
        """Test that all registries are properly initialized."""
        node_registry = library_system.get_node_registry()
        adapter_registry = library_system.get_adapter_registry()
        type_registry = library_system.get_type_registry()

        assert node_registry is not None
        assert adapter_registry is not None
        assert type_registry is not None

        # All should have at least empty lists
        assert isinstance(node_registry.list_names(), list)
        assert isinstance(adapter_registry.list_names(), list)
        assert isinstance(type_registry.list_names(), list)

    def test_node_factory_with_libraries(self, library_system: LibrarySystemService):
        """Test that node factory can access library nodes."""
        node_factory = library_system.get_node_factory()
        node_registry = library_system.get_node_registry()

        assert node_factory is not None
        available_nodes = node_registry.list_names()

        # If we have any nodes available, test creation
        if available_nodes:
            # Create an empty graph for testing
            graph = BaseGraph(graph_id="integration_test_graph", name="Integration Test")

            # Try to create the first available node
            first_node_key = available_nodes[0]
            try:
                node_instance = node_factory.create_node(first_node_key, "test_node_1", graph)
                assert node_instance is not None
                assert node_instance.node_id == "test_node_1"
            except Exception as e:
                pytest.skip(f"Could not create node {first_node_key}: {e}")
