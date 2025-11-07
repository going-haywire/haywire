"""
Test Library for Haywire

Minimal test library to demonstrate multi-library support.
Contains one node, one widget, one adapter, and one data struct.
"""

from pathlib import Path
from haywire.core.library.library import BaseLibrary
from haywire.core.library.library import library
from haywire.core.library.registries.reg_renderer import RendererRegistry
from haywire.core.library.registries.reg_adapter import AdapterRegistry
from haywire.core.library.registries.reg_widget import WidgetRegistry
from haywire.core.library.registries.reg_node import NodeRegistry

@library(
    label='Example',
    id='example',
    version='0.1.0',
    description='Example library for demonstrating multi-library support',
    url='https://github.com/author/haywire_library',
    help_url='https://docs.github.io/haywire_library',
    author='Example Author',
    author_url='https://author_url',
    dependencies=['haywire.core'],
    file_watcher=False
)
class Library(BaseLibrary):
    """Example library implementation"""
       
    def register_components(self):
        """Register all test components with the global registries"""

        """Register nodes and custom types"""
        base_path = Path(__file__).parent

        # Register adapters 
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
        """Validate that the test library is properly structured"""
        return True
