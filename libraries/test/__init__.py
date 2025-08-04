"""
Test Library for Haywire

Minimal test library to demonstrate multi-library support.
Contains one node, one widget, one adapter, and one data struct.
"""

import sys
import os

# Add project paths for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from haywire.libraries.base import BaseLibrary, LibraryMetadata
from haywire.libraries.registry import WidgetRegistry, AdapterRegistry

# Import test components
from .widgets import register_test_widgets
from .adapters import register_test_adapters
from .nodes import register_test_nodes
from .data import *  # Import test data definitions


# Library metadata
LIBRARY_METADATA = {
    'name': 'test',
    'version': '0.1.0',
    'description': 'Test library for demonstrating multi-library support',
    'author': 'Test Author',
    'dependencies': ['core']  # Depends on core library
}


class Library(BaseLibrary):
    """Test library implementation"""
    
    def __init__(self, metadata: LibraryMetadata):
        super().__init__(metadata)
    
    def register_components(self, widget_registry: WidgetRegistry, adapter_registry: AdapterRegistry, node_registry):
        """Register all test components with the global registries"""
        # Register widgets
        register_test_widgets(widget_registry)
        
        # Register adapters
        register_test_adapters(adapter_registry)
        
        # Register nodes
        register_test_nodes(node_registry)
    
    def validate(self) -> bool:
        """Validate that the test library is properly structured"""
        return True
