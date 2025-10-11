"""
Haywire Core Library

Contains fundamental nodes, widgets, adapters, and data definitions
that form the foundation of the Haywire system.
"""

from haywire.core.inventory.library import BaseLibrary
from haywire.core.inventory.registry.renderer_reg import RendererRegistry
from haywire.core.inventory.registry.adapter_reg import AdapterRegistry
from haywire.core.inventory.registry.widget_reg import WidgetRegistry
from haywire.core.inventory.base import LibraryMetadata
from haywire.core.inventory.registry.node_reg import NodeRegistry

# Import core components
from .widgets import register_widgets
from .adapters import register_adapters
from .nodes import register_nodes
from .renderers import register_renderers

# Library metadata
LIBRARY_METADATA = {
    'name': 'haywire.core',
    'version': '1.0.0',
    'description': 'Core Haywire library with fundamental components',
    'url': 'https://github.com/maybites/haywire',
    'help_url': 'https://github.com/maybites/haywire',
    'author': 'maybites',
    'author_url': 'https://maybites.ch',
    'dependencies': [],
    'file_watcher': False  # Enable file watching for this library
}

class Library(BaseLibrary):
    """Core Haywire library implementation"""

    def register_components(self):
        """Register all core components with the global registries"""
        # Register widgets
        register_widgets(self)
        
        # Register adapters (now includes data types)
        register_adapters(self)
        
        # Register renderers (node renderers)
        register_renderers(self)
        
        # Register nodes
        register_nodes(self)

    def validate(self) -> bool:
        """Validate that the core library is properly structured"""
        # Core library is always valid since it's part of the system
        return True
