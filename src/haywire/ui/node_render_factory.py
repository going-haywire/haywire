"""
NodeRenderFactory - Factory for creating UINodeCard instances using NodeRenderer classes

This factory manages cached NodeRenderer instances and provides the generate_node method
that looks up renderers from the renderers registry.
"""

from typing import Dict, Type
from haywire.core.node.base_node import BaseNode
from haywire.core.library.registries.reg_widget import WidgetRegistry
from haywire.core.library.registries.reg_renderer import RendererRegistry
from haywire.core.ui.base_renderer import BaseNodeRenderer
from haywire.core.ui.base import UINodeCard

class NodeRenderFactory:
    """
    Factory class for creating UINodeCard instances using NodeRenderer classes.
    
    This factory:
    - Has access to both renderers registry and widgets registry
    - Caches stateless NodeRenderer instances for reuse
    - Provides generate_node method for creating UINodeCard instances
    """
    
    def __init__(self, renderers_registry: RendererRegistry, widget_registry: WidgetRegistry):
        """
        Initialize the factory with registries.
        
        Args:
            renderers_registry: Registry for NodeRenderer classes
            widget_registry: Registry for widget classes (passed to NodeRenderer)
        """
        self.renderers_registry = renderers_registry
        self.widget_registry = widget_registry
        
        # Cache for NodeRenderer instances (stateless, so can be reused)
        self._renderer_cache: Dict[str, BaseNodeRenderer] = {}
    
    def generate_node(self, node_design_name: str | None, node: BaseNode) -> UINodeCard:
        """
        Generate a UINodeCard for the given node using the specified renderer.
        
        Args:
            node_design_name: Name of the renderer to use (None for default)
            node: The HaywireNode to render
            
        Returns:
            UINodeCard containing the rendered UI and widget instances
        """
        # Get renderer class from renderers registry (with fallback)
        renderer_class = self.renderers_registry.get_renderer_class(node_design_name)
        
        # Get or create cached renderer instance
        renderer_class_name = renderer_class.__name__
        if renderer_class_name not in self._renderer_cache:
            # Create new renderer instance with widget registry
            self._renderer_cache[renderer_class_name] = renderer_class(self.widget_registry)
        
        # Get cached renderer instance
        renderer_instance = self._renderer_cache[renderer_class_name]
        
        # Call render method to create UINodeCard
        return renderer_instance.render(node)
    
    def clear_cache(self):
        """Clear the renderer instance cache."""
        self._renderer_cache.clear()
    
    def get_cached_renderers(self) -> Dict[str, BaseNodeRenderer]:
        """Get a copy of the current renderer cache for debugging."""
        return self._renderer_cache.copy()
    
    def preload_renderer(self, node_design_name: str):
        """
        Preload a renderer into the cache.
        
        Args:
            node_design_name: Name of the renderer to preload
        """
        renderer_class = self.renderers_registry.get_renderer_class(node_design_name)
        renderer_class_name = renderer_class.__name__
        
        if renderer_class_name not in self._renderer_cache:
            self._renderer_cache[renderer_class_name] = renderer_class(self.widget_registry)
