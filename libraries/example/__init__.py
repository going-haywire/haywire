"""
Test Library for Haywire

Minimal test library to demonstrate multi-library support.
Contains one node, one widget, one adapter, and one data struct.
"""

from haywire.core.library.library import BaseLibrary
from haywire.core.library.library import library
from haywire.core.library.registries.reg_renderer import RendererRegistry
from haywire.core.library.registries.reg_adapter import AdapterRegistry
from haywire.core.library.registries.reg_widget import WidgetRegistry
from haywire.core.library.registries.reg_node import NodeRegistry

# Import test components
from .widgets import register_widgets
from .adapters import register_adapters  # Now includes data types
from .nodes import register_nodes
from .renderers import register_renderers

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
        # Register widgets
        register_widgets(self)

        # Register renderers
        register_renderers(self)
        
        # Register adapters
        register_adapters(self)
        
        # Register nodes
        register_nodes(self)
    
    def validate(self) -> bool:
        """Validate that the test library is properly structured"""
        return True
