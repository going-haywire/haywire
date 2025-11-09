"""
NodeRenderFactory - Factory for creating UINodeCard instances using NodeRenderer classes

This factory manages cached NodeRenderer instances and provides the generate_node method
that looks up renderers from the renderers registry.
"""

import logging
from typing import Dict, Type, List
from haywire.core.node.base_node import BaseNode
from haywire.core.library.registries.reg_widget import WidgetRegistry
from haywire.core.library.registries.reg_renderer import RendererRegistry
from haywire.core.library.library_identity import LibraryIdentity
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
        
        # Register for hot reload notifications
        self.renderers_registry.add_customer_callback(self._on_renderer_reloaded)
        self.widget_registry.add_customer_callback(self._on_widget_reloaded)
    
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
    
    def _on_renderer_reloaded(self, registry_key: str,
                             affected_class_names: List[str],
                             library_identity: LibraryIdentity) -> None:
        """
        Customer callback for renderer hot reload events.
        
        This is called by the RendererRegistry when a renderer class is reloaded, added, or removed.
        It clears the cache for affected renderers.
        
        Args:
            registry_key: The registry key of the affected renderer
            affected_class_names: List of class names that were modified
            library_identity: The library where the change occurred
        """
        logging.info(
            f"NodeRenderFactory: Renderer reloaded - {registry_key} "
            f"(classes: {', '.join(affected_class_names)}) "
            f"from library '{library_identity.label}'"
        )
        
        # Clear cache for affected renderer classes
        for class_name in affected_class_names:
            if class_name in self._renderer_cache:
                logging.debug(f"Clearing renderer cache for: {class_name}")
                del self._renderer_cache[class_name]
    
    def _on_widget_reloaded(self, registry_key: str,
                           affected_class_names: List[str],
                           library_identity: LibraryIdentity) -> None:
        """
        Customer callback for widget hot reload events.
        
        This is called by the WidgetRegistry when a widget class is reloaded, added, or removed.
        Since widgets can be used by any renderer, we clear the entire cache.
        
        Args:
            registry_key: The registry key of the affected widget
            affected_class_names: List of class names that were modified
            library_identity: The library where the change occurred
        """
        logging.info(
            f"NodeRenderFactory: Widget reloaded - {registry_key} "
            f"(classes: {', '.join(affected_class_names)}) "
            f"from library '{library_identity.label}' - clearing all renderer cache"
        )
        
        # Clear entire cache since we don't know which renderers use this widget
        self.clear_cache()
