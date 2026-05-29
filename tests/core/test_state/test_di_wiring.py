"""Tests verifying DI wiring of LibraryStateRegistry + LibraryStateContainer."""

from haywire.core.di.config import create_haywire_injector
from haywire.core.state import LibraryStateContainer, LibraryStateRegistry


class TestDIWiring:
    def test_state_registry_is_provided_as_singleton(self):
        injector = create_haywire_injector(watch_settings=False)
        reg1 = injector.get(LibraryStateRegistry)
        reg2 = injector.get(LibraryStateRegistry)
        assert isinstance(reg1, LibraryStateRegistry)
        assert reg1 is reg2

    def test_state_container_is_provided_as_singleton(self):
        injector = create_haywire_injector(watch_settings=False)
        c1 = injector.get(LibraryStateContainer)
        c2 = injector.get(LibraryStateContainer)
        assert isinstance(c1, LibraryStateContainer)
        assert c1 is c2

    def test_container_is_subscribed_to_registry_after_initialize(self):
        """After LibrarySystemService.initialize(), the container must be in
        the registry's batch event subscriber list so lifecycle events flow."""
        from haywire.core.di.config import LibrarySystemService

        injector = create_haywire_injector(watch_settings=False)
        service = LibrarySystemService(injector)
        service.initialize()

        registry = injector.get(LibraryStateRegistry)
        container = injector.get(LibraryStateContainer)
        assert container.on_lifecycle_events in registry._batch_event_subscribers

    def test_settings_propagates_reload_to_state_registry(self):
        """settings_registry → state_registry: settings reloads cascade to state."""
        from haywire.core.di.config import LibrarySystemService
        from haywire.core.settings.registry import SettingsRegistry

        injector = create_haywire_injector(watch_settings=False)
        service = LibrarySystemService(injector)
        service.initialize()

        settings_registry = injector.get(SettingsRegistry)
        state_registry = injector.get(LibraryStateRegistry)
        assert state_registry in settings_registry._registry_subscribers

    def test_state_propagates_reload_to_node_panel_editor(self):
        """state_registry → node/panel/editor: state file changes cascade to
        consumer classes that may hold a stale class reference."""
        from haywire.core.di.config import LibrarySystemService
        from haywire.core.node.registry import NodeRegistry
        from haywire.ui.editor.registry import EditorTypeRegistry
        from haywire.ui.panel.registry import PanelRegistry

        injector = create_haywire_injector(watch_settings=False)
        service = LibrarySystemService(injector)
        service.initialize()

        state_registry = injector.get(LibraryStateRegistry)
        node_registry = injector.get(NodeRegistry)
        panel_registry = injector.get(PanelRegistry)
        editor_registry = injector.get(EditorTypeRegistry)

        assert node_registry in state_registry._registry_subscribers
        assert panel_registry in state_registry._registry_subscribers
        assert editor_registry in state_registry._registry_subscribers
