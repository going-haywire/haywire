"""
Dependency Injection configuration for Haywire.

This module sets up the DI container with all necessary providers for
registries, factories, and services.
"""

import os
import logging
from pathlib import Path
from typing import Optional, List
from injector import Injector, Module, provider, singleton

from ..inventory.registry.library_reg import LibraryRegistry
from ..inventory.registry.node_reg import NodeRegistry
from ..inventory.registry.renderer_reg import RendererRegistry
from ..inventory.registry.adapter_reg import AdapterRegistry
from ..inventory.registry.widget_reg import WidgetRegistry
from ..node.node_factory import NodeFactory
from ...ui.node_render_factory import NodeRenderFactory
from ...undo.interfaces import IHistoryManager
from ...undo.history_manager import HistoryManager
from ...undo.config import UndoConfig
from ...undo.no_op_history_manager import NoOpHistoryManager


class HaywireModule(Module):
    """
    Main DI module for Haywire system.
    
    This module provides singleton instances of all core registries,
    factories, and services used throughout the Haywire system.
    """
    
    def __init__(self, project_root: Optional[str] = None, 
                 library_paths: Optional[List[str]] = None,
                 enable_file_watching: bool = True,
                 undo_config: Optional[UndoConfig] = None):
        """
        Initialize the DI module.
        
        Args:
            project_root: Root path of the project (auto-detected if None)
            library_paths: Additional library paths to scan
            enable_file_watching: Whether to enable file watching for hot reload
            undo_config: Optional undo configuration (uses default if None)
        """
        self.project_root = project_root or self._detect_project_root()
        self.library_paths = library_paths or []
        self.enable_file_watching = enable_file_watching
        self.undo_config = undo_config
        
        # Add default library paths if not provided
        if not self.library_paths:
            self.library_paths = [
                os.path.join(self.project_root, 'src', 'haywire', 'libraries'),
                os.path.join(self.project_root, 'libraries')
            ]
    
    @provider
    @singleton
    def provide_library_registry(self) -> LibraryRegistry:
        """Provide singleton LibraryRegistry."""
        library_registry = LibraryRegistry()
        # Add all configured library paths
        for path in self.library_paths:
            library_registry.add_library_path(path)

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
    def provide_renderer_registry(self) -> RendererRegistry:
        """Provide singleton RendererRegistry."""
        return RendererRegistry()
    
    @provider
    @singleton
    def provide_node_registry(self) -> NodeRegistry:
        """Provide singleton NodeRegistry."""
        return NodeRegistry()
                
    @provider
    @singleton
    def provide_history_manager(self) -> IHistoryManager:
        """Provide HistoryManager for undo/redo operations."""
        if self.undo_config is not None:
            return HistoryManager(self.undo_config)
        # Return a no-op history manager if none configured
        return NoOpHistoryManager()
    
    @provider
    @singleton
    def provide_node_factory(self, node_registry: NodeRegistry) -> NodeFactory:
        """Provide NodeFactory as pure utility."""
        return NodeFactory(node_registry)
    
    @provider
    @singleton
    def provide_node_render_factory(self, renderer_registry: RendererRegistry, 
                                   widget_registry: WidgetRegistry) -> NodeRenderFactory:
        """Provide NodeRenderFactory."""
        return NodeRenderFactory(renderer_registry, widget_registry)
    
    def _detect_project_root(self) -> str:
        """Auto-detect project root by looking for pyproject.toml."""
        current_dir = Path(__file__).parent
        
        # Walk up the directory tree looking for pyproject.toml
        while current_dir != current_dir.parent:
            if (current_dir / 'pyproject.toml').exists():
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
    
    def initialize(self) -> 'LibrarySystemService':
        """
        Initialize the library system by loading all libraries.
        
        Returns:
            Self for method chaining
        """
        if self._initialized:
            return self
        
        print("Setting up library system with DI...")
        logging.basicConfig(level=logging.INFO)
        
        # Get all required services from DI
        library_registry = self.injector.get(LibraryRegistry)
        widget_registry = self.injector.get(WidgetRegistry)
        adapter_registry = self.injector.get(AdapterRegistry)
        renderer_registry = self.injector.get(RendererRegistry)
        node_registry = self.injector.get(NodeRegistry)
        
        # Link registries to library registry for management
        library_registry.add_class_registry(WidgetRegistry, widget_registry)
        library_registry.add_class_registry(AdapterRegistry, adapter_registry)
        library_registry.add_class_registry(RendererRegistry, renderer_registry)
        library_registry.add_class_registry(NodeRegistry, node_registry)
        
        library_registry.load_libraries()

        self._initialized = True
        print(f"Library system initialized successfully.")
        
        return self
    
    def print_registry_status(self) -> None:
        """Print the status of all registries in a beautiful format."""
        adapter_registry = self.injector.get(AdapterRegistry)
        widget_registry = self.injector.get(WidgetRegistry)
        renderer_registry = self.injector.get(RendererRegistry)
        node_registry = self.injector.get(NodeRegistry)
        
        print("\n=== Registry Status ===")
        
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
        
        # Print registered renderers
        print("\n🔨 Registered Renderers:")
        all_renderers = renderer_registry.list_names()
        for renderer_key in all_renderers:
            print(f"   • {renderer_key}")
        
        # Print registered nodes
        print("\n🛠 Registered Nodes:")
        all_nodes = node_registry.list_names()
        for node_key in all_nodes:
            print(f"   • {node_key}")
        
        print(f"\nTotal: {len(all_nodes)} nodes, {len(all_renderers)} renderers, "
              f"{len(all_widgets)} widgets, {len(all_adapters)} adapters\n")
    
    # Convenience methods for getting common services
    def get_node_registry(self) -> NodeRegistry:
        """Get the node registry."""
        return self.injector.get(NodeRegistry)
    
    def get_renderer_registry(self) -> RendererRegistry:
        """Get the renderer registry."""
        return self.injector.get(RendererRegistry)
    
    def get_widget_registry(self) -> WidgetRegistry:
        """Get the widget registry."""
        return self.injector.get(WidgetRegistry)
    
    def get_adapter_registry(self) -> AdapterRegistry:
        """Get the adapter registry."""
        return self.injector.get(AdapterRegistry)
    
    def get_node_factory(self) -> NodeFactory:
        """Get the node factory."""
        return self.injector.get(NodeFactory)
    
    def get_node_render_factory(self) -> NodeRenderFactory:
        """Get the node render factory."""
        return self.injector.get(NodeRenderFactory)
    
    def get_history_manager(self) -> Optional[IHistoryManager]:
        """Get the history manager (None if no-op)."""
        manager = self.injector.get(IHistoryManager)
        return None if isinstance(manager, NoOpHistoryManager) else manager


def create_haywire_injector(project_root: Optional[str] = None,
                           library_paths: Optional[List[str]] = None,
                           enable_file_watching: bool = True,
                           undo_config: Optional[UndoConfig] = None) -> Injector:
    """
    Create and configure a Haywire DI injector.
    
    Args:
        project_root: Root path of the project (auto-detected if None)
        library_paths: Additional library paths to scan
        enable_file_watching: Whether to enable file watching for hot reload
        undo_config: Optional undo configuration for history manager
        
    Returns:
        Configured DI injector
    """
    module = HaywireModule(
        project_root=project_root,
        library_paths=library_paths,
        enable_file_watching=enable_file_watching,
        undo_config=undo_config
    )
    
    return Injector([module])


def create_library_system_service(project_root: Optional[str] = None,
                                 library_paths: Optional[List[str]] = None,
                                 enable_file_watching: bool = True,
                                 undo_config: Optional[UndoConfig] = None) -> LibrarySystemService:
    """
    Create and initialize a complete library system service.
    
    This is a convenience function that creates the DI injector, creates the service,
    and initializes the library system in one call.
    
    Args:
        project_root: Root path of the project (auto-detected if None)
        library_paths: Additional library paths to scan  
        enable_file_watching: Whether to enable file watching for hot reload
        undo_config: Optional undo configuration for history manager
        
    Returns:
        Initialized LibrarySystemService
    """
    injector = create_haywire_injector(
        project_root=project_root,
        library_paths=library_paths,
        enable_file_watching=enable_file_watching,
        undo_config=undo_config
    )
    
    service = LibrarySystemService(injector)
    service.initialize()
    
    return service
