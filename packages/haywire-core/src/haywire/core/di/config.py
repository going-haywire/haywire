# haywire/core/di/config.py
"""
Dependency Injection configuration for Haywire.

This module sets up the DI container with all necessary providers for
registries, factories, and services.
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from injector import Injector, Module, provider, singleton

from ..debug.configurator import LoggingConfigurator
from ...ui.skin.registry import SkinRegistry
from ...ui.widget.registry import WidgetRegistry
from ...ui.skin.factory import SkinFactory
from ...ui.widget.factory import WidgetFactory
from ...ui.themes.registry import ThemeRegistry
from ...ui.editor.registry import EditorTypeRegistry
from ...ui.panel.registry import PanelRegistry

from ..library.registry import LibraryRegistry
from ..node.registry import NodeRegistry
from ..adapter.registry import AdapterRegistry
from ..adapter.factory import AdapterFactory
from ..types.registry import TypeRegistry
from ..node.factory import NodeFactory
from ..settings import SettingsRegistry
from ..state import LibraryStateContainer, LibraryStateRegistry
from ..session.session_manager import SessionManager
from .context import (
    set_node_factory,
    set_adapter_factory,
    set_library_state_container,
    set_type_registry,
    set_settings_registry,
    set_session_manager,
)


class HaywireModule(Module):
    """
    Main DI module for Haywire system.

    This module provides singleton instances of all core registries,
    factories, and services used throughout the Haywire system.
    """

    def __init__(
        self,
        workspace_root: Optional[str] = None,
        library_paths: Optional[List[str]] = None,
        enable_file_watching: bool = True,
        settings_path: Optional[str] = None,
        watch_settings: bool = True,
    ):
        """
        Initialize the DI module.

        Args:
            workspace_root:     Root path of the workspace (auto-detected if None).
            library_paths:      Additional library paths to scan.
            enable_file_watching: Whether to enable file watching for hot reload.
            settings_path:      Path to the global settings TOML file
                                (default: ~/.haywire/settings.toml, hand-edited by user).
            watch_settings:     Whether to watch settings files for hot reload.
        """
        self.workspace_root = workspace_root or self._detect_project_root()
        self.library_paths = library_paths or []
        self.enable_file_watching = enable_file_watching
        self.watch_settings = watch_settings

        # Global-tier settings path (hand-edited by user, never written by the app)
        if settings_path:
            self.settings_path = Path(settings_path).expanduser().resolve()
        else:
            self.settings_path = Path.home() / ".haywire" / "settings.toml"

        # Library paths must be explicitly provided by the app or test config.
        # The framework does not assume a particular workspace layout.

    @provider
    @singleton
    def provide_settings_registry(self) -> SettingsRegistry:
        """
        Provide singleton SettingsRegistry.

        Initialization order:
        1. Register built-in setting definitions (schema only, no values).
        2. Load global tier from ~/.haywire/settings.toml (hand-edited by user).
        3. Load workspace tier from <workspace>/.haywire/settings.toml (written by UI).
        4. Optionally watch both files for hot-reload.
        """
        registry = SettingsRegistry()

        # Global tier — hand-edited by user, never overwritten by the app
        registry.load_from_toml(self.settings_path, tier="global", watch=self.watch_settings)

        # Workspace tier — managed by the UI, saved via registry.save_to_toml()
        workspace_settings = Path(self.workspace_root) / ".haywire" / "settings.toml"
        registry.load_from_toml(workspace_settings, tier="workspace", watch=self.watch_settings)

        set_settings_registry(registry)
        return registry

    @provider
    @singleton
    def provide_library_registry(self) -> LibraryRegistry:
        """Provide singleton LibraryRegistry."""
        library_registry = LibraryRegistry()

        # Core libraries are not used (loaded via pip entry points instead)
        library_registry.load_core_libraries = False

        # Enable pip package discovery (priority 2 & 3)
        library_registry.load_pip_packages = True

        # Add all configured library paths (priority 4)
        for path in self.library_paths:
            library_registry.add_library_root_path(path)

        # Enable file watching if requested
        if self.enable_file_watching:
            library_registry.enable_file_watching(debounce_delay=0.5, force=True)

        return library_registry

    @provider
    @singleton
    def provide_widget_registry(self) -> WidgetRegistry:
        """Provide singleton WidgetRegistry."""
        return WidgetRegistry()

    @provider
    @singleton
    def provide_adapter_registry(self) -> AdapterRegistry:
        """Provide singleton AdapterRegistry."""
        return AdapterRegistry()

    @provider
    @singleton
    def provide_skin_registry(self) -> SkinRegistry:
        """Provide singleton SkinRegistry."""
        return SkinRegistry()

    @provider
    @singleton
    def provide_node_registry(self) -> NodeRegistry:
        """Provide singleton NodeRegistry."""
        return NodeRegistry()

    @provider
    @singleton
    def provide_type_registry(self) -> TypeRegistry:
        """Provide singleton TypeRegistry."""
        registry = TypeRegistry()
        set_type_registry(registry)
        return registry

    @provider
    @singleton
    def provide_editor_type_registry(self) -> EditorTypeRegistry:
        """Provide singleton EditorTypeRegistry.

        All editors are registered in haywire-app/app.py after injector creation.
        """
        registry = EditorTypeRegistry()
        return registry

    @provider
    @singleton
    def provide_panel_registry(self) -> PanelRegistry:
        """Provide singleton PanelRegistry."""
        return PanelRegistry()

    @provider
    @singleton
    def provide_library_state_registry(self) -> LibraryStateRegistry:
        """Provide singleton LibraryStateRegistry — class registry for LibraryState subclasses."""
        return LibraryStateRegistry()

    @provider
    @singleton
    def provide_library_state_container(self, state_registry: LibraryStateRegistry) -> LibraryStateContainer:
        """Provide singleton LibraryStateContainer — instance pool for LibraryStates.

        Holds the state_registry so on_library_enabled / catch-up can query
        it without an extra argument every call. Subscription to event
        channels is wired separately by LibrarySystemService.initialize()
        via container.bind_to_lifecycle(library_registry), AFTER
        enable_all_libraries() has returned (timing matters: subscribing
        earlier would defeat the load-order fix).

        Also publishes via set_library_state_container() so AppState authors
        can read it from ambient context (e.g. for constructing Interpreters).
        """
        container = LibraryStateContainer(state_registry)
        set_library_state_container(container)
        return container

    @provider
    @singleton
    def provide_session_manager(self, container: LibraryStateContainer) -> SessionManager:
        """Provide singleton SessionManager.

        Also publishes the instance to the ambient DI context so deep callers
        (AppState.on_enable) can read it without constructor injection.
        """
        manager = SessionManager(container=container)
        set_session_manager(manager)
        return manager

    @provider
    @singleton
    def provide_node_factory(self, node_registry: NodeRegistry) -> NodeFactory:
        """Provide NodeFactory as pure utility."""
        factory = NodeFactory(node_registry)
        set_node_factory(factory)
        return factory

    @provider
    @singleton
    def provide_adapter_factory(self, adapter_registry: AdapterRegistry) -> AdapterFactory:
        """Provide AdapterFactory for creating adapter chains."""
        factory = AdapterFactory(adapter_registry)
        set_adapter_factory(factory)
        return factory

    @provider
    @singleton
    def provide_widget_factory(self, widget_registry: WidgetRegistry) -> WidgetFactory:
        """Provide singleton WidgetFactory."""
        return WidgetFactory(widget_registry)

    @provider
    @singleton
    def provide_skin_factory(
        self, skin_registry: SkinRegistry, widget_factory: WidgetFactory
    ) -> SkinFactory:
        """Provide SkinFactory."""
        return SkinFactory(skin_registry, widget_factory)

    @provider
    @singleton
    def provide_theme_registry(self) -> ThemeRegistry:
        """Provide singleton ThemeRegistry.

        Themes are registered by haybale-core via register_components() when libraries load.
        """
        return ThemeRegistry()

    # -------------------------------------------------------------------------
    def _detect_project_root(self) -> str:
        """Auto-detect project root by looking for pyproject.toml."""
        current_dir = Path(__file__).parent

        # Walk up the directory tree looking for pyproject.toml
        while current_dir != current_dir.parent:
            if (current_dir / "pyproject.toml").exists():
                return str(current_dir)
            current_dir = current_dir.parent

        # Fallback to current working directory
        return os.getcwd()


class LibrarySystemService:
    """
    Service that handles library system initialization and provides easy access to components.

    This service encapsulates the complexity of setting up the library discovery system
    and loading all libraries into the appropriate registries.
    """

    def __init__(self, injector: Injector):
        """
        Initialize with DI injector.

        Args:
            injector: The configured DI injector
        """
        self.injector = injector
        self._initialized = False

    def initialize(self) -> "LibrarySystemService":
        """
        Initialize the library system by loading all libraries.

        Returns:
            Self for method chaining
        """
        if self._initialized:
            return self

        print("=" * 70)
        print("Initializing Haywire Library System")
        print("=" * 70)
        logging.basicConfig(level=logging.INFO)

        # Get all required services from DI — order matters for ambient context:
        # TypeRegistry and SettingsRegistry are used by BaseNode constructors,
        # NodeFactory by NodeWrapper, AdapterFactory by EdgeWrapper. All four must be
        # eagerly resolved here so their providers set the context vars before any
        # graph/node construction can happen.
        settings_registry = self.injector.get(
            SettingsRegistry
        )  # must be first — wires FrameworkSettings._registry and loads TOML
        self._logging_configurator = LoggingConfigurator(settings_registry)
        library_registry = self.injector.get(LibraryRegistry)
        theme_registry = self.injector.get(ThemeRegistry)
        type_registry = self.injector.get(TypeRegistry)
        adapter_registry = self.injector.get(AdapterRegistry)
        widget_registry = self.injector.get(WidgetRegistry)
        node_registry = self.injector.get(NodeRegistry)
        skin_registry = self.injector.get(SkinRegistry)
        panel_registry = self.injector.get(PanelRegistry)
        editor_registry = self.injector.get(EditorTypeRegistry)
        library_state_registry = self.injector.get(LibraryStateRegistry)
        library_state_container = self.injector.get(LibraryStateContainer)
        # NOTE: container subscription + library_enabled callback + startup
        # catch-up are wired AFTER enable_all_libraries() below, not here.
        # See "Wire LibraryStateContainer to events ..." section.
        self.injector.get(AdapterFactory)  # sets ambient context for EdgeWrapper
        self.injector.get(NodeFactory)  # sets ambient context for NodeWrapper
        self.injector.get(SessionManager)  # sets ambient context for AppState.on_enable

        # Link registries to library registry for management
        library_registry.add_class_registry(ThemeRegistry, theme_registry)
        library_registry.add_class_registry(SettingsRegistry, settings_registry)
        library_registry.add_class_registry(TypeRegistry, type_registry)
        library_registry.add_class_registry(AdapterRegistry, adapter_registry)
        library_registry.add_class_registry(WidgetRegistry, widget_registry)
        library_registry.add_class_registry(NodeRegistry, node_registry)
        library_registry.add_class_registry(SkinRegistry, skin_registry)
        library_registry.add_class_registry(PanelRegistry, panel_registry)
        library_registry.add_class_registry(EditorTypeRegistry, editor_registry)
        library_registry.add_class_registry(LibraryStateRegistry, library_state_registry)

        # Set up registry subscribers for cross-registry updates
        # this ensures that when new types are added,
        # nodes, widgets and adapters are updated accordingly
        type_registry.add_registry_subscriber(adapter_registry)
        type_registry.add_registry_subscriber(widget_registry)
        type_registry.add_registry_subscriber(node_registry)

        # When a LibrarySettings file changes on disk (hot-reload), propagate the
        # FileChangeEvent downstream so any module that imports from it gets reloaded.
        # This mirrors the type_registry → node_registry pattern.

        settings_registry.add_registry_subscriber(library_state_registry)
        settings_registry.add_registry_subscriber(node_registry)
        settings_registry.add_registry_subscriber(skin_registry)
        settings_registry.add_registry_subscriber(panel_registry)
        settings_registry.add_registry_subscriber(editor_registry)

        library_state_registry.add_registry_subscriber(node_registry)
        library_state_registry.add_registry_subscriber(panel_registry)
        library_state_registry.add_registry_subscriber(editor_registry)

        print("\n🔍 Scanning for libraries...")
        library_registry.scan_for_libraries()

        # Apply persisted-disabled state BEFORE the enable phase, so libraries
        # the user previously disabled never enter the enable cycle in the
        # first place. Owning this step here — rather than on a LibraryManager
        # post-hook — avoids a mid-bootstrap mutation cascade. See ADR-0001.
        from haywire.core.di.context import get_workspace_root
        from haywire.core.library.disabled_state_io import read_disabled_ids

        try:
            workspace_root: Path | None = get_workspace_root()
        except RuntimeError:
            workspace_root = None
        if workspace_root is not None:
            disabled_ids = read_disabled_ids(workspace_root)
            known = set(library_registry.list_names())
            for lib_id in disabled_ids:
                if lib_id in known:
                    library_registry.disable_library(lib_id)

        # Wire LibraryStateContainer before enabling libraries so that
        # on_library_enabled fires naturally for each library as it enables.
        # CLASS_ADDED events during enable() only instantiate state (phase 1);
        # on_library_enabled triggers on_enable (phase 2) once all of that
        # library's components are registered.
        library_state_container.bind_to_lifecycle(library_registry)

        print("\n⚡ Enabling libraries...")
        library_registry.enable_all_libraries()

        # Print detailed library discovery results
        self._print_library_discovery_results()

        # Print registry status
        print("\n📋 Registry Status:")
        print("-" * 70)
        self.print_registry_status()

        # Print settings status
        print("\n⚙️  Settings Status:")
        print("-" * 70)
        self._print_settings_status(settings_registry)

        self._initialized = True
        print("\n" + "=" * 70)
        print("✅ Library system initialized successfully!")
        print("=" * 70 + "\n")

        return self

    def _print_settings_status(self, registry: SettingsRegistry) -> None:
        """Print settings registry status."""
        from ..settings import SettingMode

        definitions = registry.all_definitions()
        categories = registry.definitions_by_category()

        # Count overrides and custom values
        overrides = 0
        custom_values = 0
        for name in definitions:
            sv = registry.get_global(name)
            if sv.mode == SettingMode.OVERRIDE:
                overrides += 1
            elif sv.mode == SettingMode.EXPLICIT:
                custom_values += 1

        print(f"   Total settings:     {len(definitions)}")
        print(f"   Categories:         {len(categories)}")
        print(f"   Custom values:      {custom_values}")
        print(f"   Global overrides:   {overrides}")
        print(f"   Global tier:        {registry._global_path}")
        print(f"   Workspace tier:     {registry._workspace_path}")
        print(
            f"   File watching:      "
            f"global={'on' if registry._global_watch_enabled else 'off'}, "
            f"workspace={'on' if registry._workspace_watch_enabled else 'off'}"
        )

        # List categories
        print("\n   Categories:")
        for cat_name, defns in sorted(categories.items()):
            print(f"      • {cat_name}: {len(defns)} settings")

    def _print_library_discovery_results(self) -> None:
        """Print detailed information about discovered libraries."""
        library_registry = self.injector.get(LibraryRegistry)

        print("\n📊 Library Discovery Results:")
        print("-" * 70)

        # Test entry point discovery directly
        print("\n🔍 Entry Point Discovery:")
        print("-" * 70)

        from haywire.core.library.discovery import LibraryDiscovery

        discovered = LibraryDiscovery.discover_installed_libraries()

        if discovered:
            print(f"\n✅ Found {len(discovered)} libraries via entry points:\n")

            for lib_info in discovered:
                print(f"  • {lib_info.identity.label} ({lib_info.identity.id})")
                print(f"      Type: {lib_info.install_type.value}")
                print(f"      Path: {lib_info.library_path}")
                if lib_info.entry_point_name:
                    print(f"      Entry Point: {lib_info.entry_point_name}")
                print()
        else:
            print("ℹ️  No libraries found via entry points")
            print("   (This is normal if libraries aren't pip installed)")

        print("-" * 70)

        # List all loaded libraries
        loaded_libraries = library_registry.list_names()

        if not loaded_libraries:
            print("⚠️  No libraries loaded!")
            return

        print(f"\n✅ Loaded {len(loaded_libraries)} libraries:\n")

        for lib_id in loaded_libraries:
            identity = library_registry.get_library_identity(lib_id)
            source = library_registry.get_library_source(lib_id)
            install_type = library_registry.get_library_install_type(lib_id)
            enabled = library_registry.is_library_enabled(lib_id)

            # Determine how the library was added
            install_method = "❓ Unknown"
            if install_type:
                from haywire.core.library.discovery import InstallType

                if install_type == InstallType.REGULAR:
                    install_method = "📦 Pip (regular install)"
                elif install_type == InstallType.EDITABLE:
                    install_method = "🔗 Pip (editable install)"
                elif install_type == InstallType.FOLDER:
                    # Determine if it's core or search path
                    if source and "src/haywire/libraries" in source:
                        install_method = "⭐ Core library"
                    else:
                        install_method = "📁 Search path"

            status = "✓" if enabled else "✗"
            print(f"  {status} {identity.label}")
            print(f"      ID:             {lib_id}")
            print(f"      Version:        {identity.version}")
            print(f"      Enabled:        {enabled}")
            print(f"      Dependencies:   {identity.dependencies}")
            print(f"      Source:         {source}")
            print(f"      Install Method: {install_method}")
            print()

        print("-" * 70)

    def print_registry_status(self) -> None:
        """Print the status of all registries in a beautiful format."""
        adapter_registry = self.injector.get(AdapterRegistry)
        widget_registry = self.injector.get(WidgetRegistry)
        skin_registry = self.injector.get(SkinRegistry)
        node_registry = self.injector.get(NodeRegistry)
        type_registry = self.injector.get(TypeRegistry)
        editor_registry = self.injector.get(EditorTypeRegistry)
        panel_registry = self.injector.get(PanelRegistry)
        theme_registry = self.injector.get(ThemeRegistry)
        self.injector.get(SettingsRegistry)
        library_registry = self.injector.get(LibraryRegistry)

        # Print registered libraries
        print("\n📚 Registered Libraries:")
        all_libraries = library_registry.list_names()
        for lib_key in all_libraries:
            print(f"   • {lib_key}")

        # Print registered nodes
        print("\n🛠 Registered Nodes:")
        all_nodes = node_registry.list_names()
        for node_key in all_nodes:
            print(f"   • {node_key}")

        # Print registered custom types
        print("\n📦 Registered Types:")
        all_types = type_registry.list_names()
        for type_key in all_types:
            print(f"   • {type_key}")

        # Print registered adapters
        print("\n🔗 Registered Adapters:")
        all_adapters = adapter_registry.list_names()
        for adapter_key in all_adapters:
            print(f"   • {adapter_key}")

        # Print registered widgets
        print("\n🔧 Registered Widgets:")
        all_widgets = widget_registry.list_names()
        for widget_key in all_widgets:
            print(f"   • {widget_key}")

        # Print registered skins
        print("\n🎨 Registered Skins:")
        all_skins = skin_registry.list_names()
        for skin_key in all_skins:
            print(f"   • {skin_key}")

        # Print registered editors
        print("\n🖥 Registered Editors:")
        all_editors = editor_registry.list_names()
        for editor_key in all_editors:
            print(f"   • {editor_key}")

        # Print registered panels grouped by focus
        print("\n📋 Registered Panels:")
        all_panels = panel_registry.list_names()
        by_focus: Dict[str, list] = {}
        for panel_key in all_panels:
            cls = panel_registry.get(panel_key)
            if cls is None:
                continue
            focus = getattr(cls.class_identity, "focus", None)
            focus_id = getattr(focus, "id", "?") if focus is not None else "?"
            by_focus.setdefault(focus_id, []).append((panel_key, cls))
        for focus_id in sorted(by_focus):
            print(f"   {focus_id}:")
            for panel_key, cls in by_focus[focus_id]:
                action = getattr(cls.class_identity, "action", None)
                action_name = getattr(action, "__name__", "?") if action is not None else "?"
                print(f"      • {panel_key}  ({action_name})")

        # Print registered themes
        print("\n🌈 Registered Themes:")
        all_workbench_themes = theme_registry.list_workbench_keys()
        for theme_key in all_workbench_themes:
            print(f"   • {theme_key} (workbench)")
        all_node_themes = theme_registry.list_node_theme_keys()
        for theme_key in all_node_themes:
            print(f"   • {theme_key} (node)")

        print(
            f"\nTotal: {len(all_libraries)} libraries, {len(all_nodes)} nodes, "
            f"{len(all_types)} types, {len(all_adapters)} adapters, "
            f"{len(all_widgets)} widgets, {len(all_skins)} skins, "
            f"{len(all_editors)} editors, {len(all_panels)} panels, "
            f"{len(all_workbench_themes) + len(all_node_themes)} themes "
        )

    # =========================================================================
    # Convenience methods for getting common services
    # =========================================================================

    def get_node_registry(self) -> NodeRegistry:
        """Get the node registry."""
        return self.injector.get(NodeRegistry)

    def get_skin_registry(self) -> SkinRegistry:
        """Get the skin registry."""
        return self.injector.get(SkinRegistry)

    def get_widget_registry(self) -> WidgetRegistry:
        """Get the widget registry."""
        return self.injector.get(WidgetRegistry)

    def get_adapter_registry(self) -> AdapterRegistry:
        """Get the adapter registry."""
        return self.injector.get(AdapterRegistry)

    def get_type_registry(self) -> TypeRegistry:
        """Get the type registry."""
        return self.injector.get(TypeRegistry)

    def get_library_registry(self) -> LibraryRegistry:
        """Get the library registry."""
        return self.injector.get(LibraryRegistry)

    def get_node_factory(self) -> NodeFactory:
        """Get the node factory."""
        return self.injector.get(NodeFactory)

    def get_adapter_factory(self) -> AdapterFactory:
        """Get the adapter factory."""
        return self.injector.get(AdapterFactory)

    def get_skin_factory(self) -> SkinFactory:
        """Get the skin factory."""
        return self.injector.get(SkinFactory)

    def get_theme_registry(self) -> ThemeRegistry:
        """Get the theme registry."""
        return self.injector.get(ThemeRegistry)

    def get_settings_registry(self) -> SettingsRegistry:
        """Get the global settings registry."""
        return self.injector.get(SettingsRegistry)

    def get_panel_registry(self) -> PanelRegistry:
        """Get the panel registry."""
        return self.injector.get(PanelRegistry)

    def get_editor_registry(self) -> EditorTypeRegistry:
        """Get the editor type registry."""
        return self.injector.get(EditorTypeRegistry)

    def get_state_registry(self) -> LibraryStateRegistry:
        """Get the library state registry."""
        return self.injector.get(LibraryStateRegistry)

    # =========================================================================
    # Settings convenience methods
    # =========================================================================

    def get_setting(self, name: str) -> Any:
        """
        Get a resolved setting value.

        Args:
            name: Setting name (e.g., 'ui.node.bg_color')

        Returns:
            Resolved value
        """
        registry = self.get_settings_registry()
        value, _ = registry.resolve(name)
        return value

    def set_setting(self, name: str, value: Any, override: bool = False) -> None:
        """
        Set a global setting value.

        Args:
            name: Setting name
            value: Value to set
            override: If True, force this value on all nodes
        """
        from ..settings import SettingMode

        registry = self.get_settings_registry()
        mode = SettingMode.OVERRIDE if override else SettingMode.EXPLICIT
        registry.set_global(name, value, mode)

    def save_settings(self) -> None:
        """Save current settings to TOML file."""
        registry = self.get_settings_registry()
        registry.save_to_toml()

    def reload_settings(self) -> None:
        """Reload settings from both TOML tiers."""
        registry = self.get_settings_registry()
        if registry._global_path and registry._global_path.exists():
            registry._reload_from_file(registry._global_path, tier="global")
        if registry._workspace_path and registry._workspace_path.exists():
            registry._reload_from_file(registry._workspace_path, tier="workspace")


def create_haywire_injector(
    workspace_root: Optional[str] = None,
    library_paths: Optional[List[str]] = None,
    enable_file_watching: bool = True,
    settings_path: Optional[str] = None,
    watch_settings: bool = True,
) -> Injector:
    """
    Create and configure a Haywire DI injector.

    Args:
        workspace_root:       Root path of the workspace (auto-detected if None).
        library_paths:        Additional library paths to scan.
        enable_file_watching: Whether to enable file watching for hot reload.
        settings_path:        Path to the global settings TOML file
                              (default: ~/.haywire/settings.toml).
        watch_settings:       Whether to watch settings files for hot reload.

    Returns:
        Configured DI injector.
    """
    module = HaywireModule(
        workspace_root=workspace_root,
        library_paths=library_paths,
        enable_file_watching=enable_file_watching,
        settings_path=settings_path,
        watch_settings=watch_settings,
    )

    return Injector([module])


def create_library_system_service(
    workspace_root: Optional[str] = None,
    library_paths: Optional[List[str]] = None,
    enable_file_watching: bool = True,
    settings_path: Optional[str] = None,
    watch_settings: bool = True,
) -> LibrarySystemService:
    """
    Create and initialize a complete library system service.

    Convenience function that creates the DI injector, creates the service,
    and initializes the library system in one call.

    Args:
        workspace_root:       Root path of the workspace (auto-detected if None).
        library_paths:        Additional library paths to scan.
        enable_file_watching: Whether to enable file watching for library class hot reload.
        settings_path:        Path to the global settings TOML file
                              (default: ~/.haywire/settings.toml).
        watch_settings:       Whether to watch settings files for hot reload.

    Returns:
        Initialized LibrarySystemService.
    """
    injector = create_haywire_injector(
        workspace_root=workspace_root,
        library_paths=library_paths,
        enable_file_watching=enable_file_watching,
        settings_path=settings_path,
        watch_settings=watch_settings,
    )

    service = LibrarySystemService(injector)
    service.initialize()

    return service


# ============================================================================
# Global Helper Functions for DI Access
# ============================================================================

_global_injector: Optional[Injector] = None
_global_library_system: Optional[LibrarySystemService] = None


def set_global_injector(injector: Injector) -> None:
    """
    Set the global DI injector.

    This should be called during application initialization.

    Args:
        injector: The configured injector to use globally
    """
    global _global_injector
    _global_injector = injector


def set_library_system(service: LibrarySystemService | None) -> None:
    """
    Set the global LibrarySystemService.

    Should be called during application initialization.

    Args:
        service: The initialized LibrarySystemService (or None to clear)
    """
    global _global_library_system, _global_injector
    _global_library_system = service
    _global_injector = service.injector if service is not None else None


def get_library_system() -> LibrarySystemService:
    """
    Get the global LibrarySystemService.

    Returns:
        LibrarySystemService instance

    Raises:
        RuntimeError: If not initialized
    """
    if _global_library_system is None:
        raise RuntimeError(
            "LibrarySystemService not initialized. Call set_library_system() during app startup."
        )
    return _global_library_system


def get_theme_registry() -> "ThemeRegistry":
    """Get the ThemeRegistry from the global library system."""
    return get_library_system().get_theme_registry()


def get_skin_registry() -> "SkinRegistry":
    """Get the SkinRegistry from the global library system."""
    return get_library_system().get_skin_registry()


def get_settings_registry() -> SettingsRegistry:
    """
    Get the SettingsRegistry from the global library system.

    Convenience function for quick access to settings.

    Returns:
        SettingsRegistry instance

    Raises:
        RuntimeError: If library system not initialized
    """
    return get_library_system().get_settings_registry()


def get_setting(name: str) -> Any:
    """
    Get a resolved setting value.

    Convenience function for quick access to settings.

    Args:
        name: Setting name (e.g., 'ui.node.bg_color')

    Returns:
        Resolved value

    Raises:
        RuntimeError: If library system not initialized
        KeyError: If setting not found
    """
    return get_library_system().get_setting(name)


def get_adapter_factory() -> AdapterFactory:
    """
    Get the AdapterFactory from the global injector.

    Returns:
        AdapterFactory instance

    Raises:
        RuntimeError: If global injector not set
    """
    if _global_injector is None:
        raise RuntimeError("Global injector not set. Call set_global_injector() first.")
    return _global_injector.get(AdapterFactory)
