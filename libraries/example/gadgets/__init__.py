"""
Core gadgets (node renderers) registration and exports
"""

from haywire.core.registry.registry import GadgetsRegistry

# Import all renderer classes
from .example_renderer import ExampleNodeRenderer

def register_test_gadgets(gadgets_registry: GadgetsRegistry):
    """Register all core node renderers with the gadgets registry"""
    
    # Register default and error renderers
    gadgets_registry.register_renderer('example.renderer', ExampleNodeRenderer)
    
__all__ = [
    'ExampleNodeRenderer',
    'register_test_gadgets'
]
