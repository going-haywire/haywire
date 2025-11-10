"""
Test Library B for Haywire

Minimal test library to demonstrate multi-library support and for testing purposes.
Contains folders for nodes, widgets, adapters, renderers, and custom types.
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
    label='Test B',
    id='test_b',
    version='1.0.0',
    description='Test library B for demonstrating multi-library support',
    url='https://github.com/maybites/haywire',
    help_url='https://github.com/maybites/haywire',
    author='Haywire Team',
    author_url='https://github.com/maybites/haywire',
    dependencies=['haywire.libraries.core', 'test_a.types'],
    file_watcher=True
)
class Library(BaseLibrary):
    """Test B library implementation"""
       
    def register_components(self):
        """Register all test components with the global registries"""

        """Register nodes and custom types"""
        base_path = Path(__file__).parent

        # Register custom types
        self.add_folder_to_registry(
            folder_path=str(base_path / 'types'),
            registry_cls=CustomTypeRegistry
        )

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


# Export for entry point discovery
__all__ = ['Library']
