"""
Haywire Core Library

Contains fundamental nodes, widgets, adapters, and data definitions
that form the foundation of the Haywire system.
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.ui.renderer.registry import RendererRegistry
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.ui.widget.registry import WidgetRegistry
from haywire.core.node.registry import NodeRegistry
from haywire.core.types.registry import TypeRegistry

@library(
    label='Haywire Core',
    id='core',
    version='1.0.0',
    description='Core Haywire library with fundamental components',
    url='https://github.com/maybites/haywire',
    help_url='https://github.com/maybites/haywire',
    author='maybites',
    author_url='https://maybites.ch',
    dependencies=[],
    file_watcher=False
)
class Library(BaseLibrary):
    """Core Haywire library implementation"""

    def register_components(self):
        """Register all core components with the global registries"""

        """Register nodes and custom types"""
        base_path = Path(__file__).parent

        # Register types (both variants and custom types)
        self.add_folder_to_registry(
            folder_path=str(base_path / 'types'),
            registry_cls=TypeRegistry
        )

        # Register adapters (now includes data types)
        self.add_folder_to_registry(
            folder_path=str(base_path / 'adapters'),
            registry_cls=AdapterRegistry
        )
        
        # Register widgets
        self.add_folder_to_registry(
            folder_path=str(base_path / 'widgets'),
            registry_cls=WidgetRegistry
        )
                
        # Register renderers (node renderers)
        self.add_folder_to_registry(
            folder_path=str(base_path / 'renderers'),
            registry_cls=RendererRegistry
        )

        # Register nodes
        self.add_folder_to_registry(
            folder_path=str(base_path / 'nodes'),
            registry_cls=NodeRegistry
        )
        

    def validate(self) -> bool:
        """Validate that the core library is properly structured"""
        # Core library is always valid since it's part of the system
        return True
