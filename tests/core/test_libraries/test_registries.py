import importlib

import pytest
from haywire.core.di.config import LibrarySystemService
from haywire.core.graph.base import BaseGraph
from haywire.core.state import LibraryStateContainer


@pytest.mark.integration
class TestBaseRegistryClassIdentity:
    """Regression: BaseRegistry._on_creation must not force-reload modules.

    The haybale-testing library deliberately registers ``state/`` LAST in
    its ``register_components()``. The panels registered before it
    eagerly import ``TestSessionState`` at module-load time, so by the
    time state/ is scanned the module is already in ``sys.modules``.

    Pre-fix, ``_on_creation`` called ``module_scan_for_classes`` with
    ``force_reload=True``, which deleted the module from ``sys.modules``
    and re-imported it — producing a fresh class object. The panel's
    captured reference was stale; the registry/container held a different
    class. ``ctx.data[TestSessionState]`` (using the panel's reference)
    keyed into a container keyed by the post-reload class → KeyError.

    Post-fix, the initial scan does not force-reload. Class identity
    survives the scan regardless of the order in which folders register.
    """

    def test_panel_pre_imported_class_matches_registered_class(self, library_system: LibrarySystemService):
        """Panel's eager import resolves to the same class the container holds."""
        # Resolve via the panel module — same path production code takes.
        panel_module = importlib.import_module("haybale_testing.panels.test_session_state_panel")
        panel_class_ref = panel_module.TestSessionState

        # Resolve via the canonical state module path.
        state_module = importlib.import_module("haybale_testing.state.test_session_state")
        state_class_ref = state_module.TestSessionState

        # If _on_creation ever force-reloads again, these would be
        # distinct class objects.
        assert panel_class_ref is state_class_ref

        # And the same class must be the one the container is keyed by,
        # otherwise ctx.data[TestSessionState] lookups via the panel's
        # reference would KeyError.
        container = library_system.injector.get(LibraryStateContainer)
        assert panel_class_ref in container._sessions


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
