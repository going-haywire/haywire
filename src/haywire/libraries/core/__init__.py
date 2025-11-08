"""
Haywire Core Library

Contains fundamental nodes, widgets, adapters, and data definitions
that form the foundation of the Haywire system.
"""

from pathlib import Path

from haywire.core.library.library import BaseLibrary
from haywire.core.library.library import library
from haywire.core.library.registries.reg_renderer import RendererRegistry
from haywire.core.library.registries.reg_adapter import AdapterRegistry
from haywire.core.library.registries.reg_widget import WidgetRegistry
from haywire.core.library.registries.reg_node import NodeRegistry
from haywire.core.library.registries.reg_custom_type import CustomTypeRegistry

@library(
    label='Haywire Core',
    id='haywire.core',
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

        # Register custom types
        self.add_folder_to_registry(
            folder_path=str(base_path / 'types'),
            registry_cls=CustomTypeRegistry
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
