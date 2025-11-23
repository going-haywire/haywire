"""
NodeRenderFactory - Factory for creating UINodeCard instances using NodeRenderer classes

This factory manages cached NodeRenderer instances and provides the generate_node method
that looks up renderers from the renderers registry.

Enhanced with customer notification system for UINode hot reload support.
"""

import logging
from typing import Any, Dict, Type, List

from haywire.core.ui.widget.registry import WidgetRegistry
from haywire.core.ui.renderer.registry import RendererRegistry
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LiveCycleBatchCallback
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.ui.renderer.base import IBaseRenderer, IRenderFactory
from haywire.ui.ui_nodecard import NiceUINodeCard

class RenderFactory(IRenderFactory):
    """
    Factory class for creating UINodeCard instances using NodeRenderer classes.
    
    This factory:
    - Has access to both renderers registry and widgets registry
    - Caches stateless NodeRenderer instances for reuse
    - Provides generate_node method for creating UINodeCard instances
    - Notifies customers (UINodes) when renderers are hot-reloaded
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
        self._renderer_cache: Dict[str, IBaseRenderer] = {}
        
        # Customer callbacks for hot reload notifications
        self._renderer_lifecycle_subscribers: List[LiveCycleBatchCallback] = []
        
        # Register for hot reload notifications from registries
        self.renderers_registry.add_batch_event_subscriber(self._on_renderer_reloaded)
        self.widget_registry.add_batch_event_subscriber(self._on_widget_reloaded)
    
    def generate_node(self, renderer_registry_key: str | None, wrapper: NodeWrapper) -> tuple[NiceUINodeCard, str]:
        """
        Generate a UINodeCard for the given node using the specified renderer.
        
        Args:
            renderer_registry_key: Name of the renderer to use (None for default)
            wrapper: The NodeWrapper containing the HaywireNode to render
            
        Returns:
            UINodeCard containing the rendered UI and widget instances
            str: The registry key of the used renderer
        """
        # Get renderer class from renderers registry (with fallback)
        renderer_class = self.renderers_registry.get_renderer_class(renderer_registry_key)
        
        registry_key = renderer_class.class_identity.registry_key

        # Get or create cached renderer instance
        renderer_class_name = renderer_class.__name__
        if registry_key not in self._renderer_cache:
            # Create new renderer instance with widget registry
            self._renderer_cache[registry_key] = renderer_class(self)
        
        # Get cached renderer instance
        renderer_instance = self._renderer_cache[registry_key]
        
        # Call render method to create UINodeCard
        return renderer_instance.render(wrapper)
    
    def clear_cache(self):
        """Clear the renderer instance cache."""
        self._renderer_cache.clear()
    
    def get_cached_renderers(self) -> Dict[str, IBaseRenderer]:
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
    
    def add_renderer_lifecycle_subscriber(self, callback: LiveCycleBatchCallback) -> None:
        """
        Register a customer callback for renderer hot reload notifications.
        
        Callbacks are invoked when a renderer is hot-reloaded, added, or removed.
        
        Args:
            callback: Function with signature (event: list[LifeCycleEvent]) -> None
        """
        if callback not in self._renderer_lifecycle_subscribers:
            self._renderer_lifecycle_subscribers.append(callback)
            logging.debug(f"Added customer callback to NodeRenderFactory: {callback}")
    
    def remove_renderer_lifecycle_subscriber(self, callback: LiveCycleBatchCallback) -> None:
        """
        Unregister a customer callback.
        
        Args:
            callback: The callback function to remove
        """
        if callback in self._renderer_lifecycle_subscribers:
            self._renderer_lifecycle_subscribers.remove(callback)
            logging.debug(f"Removed customer callback from NodeRenderFactory: {callback}")
    
    def _notify_subscribers(self, event: LifeCycleEvent) -> None:
        """
        Notify all registered customers about renderer changes.
        
        Args:
            event: The hot reload event with complete context
        """
        for callback in self._renderer_lifecycle_subscribers[:]:  # Copy list to avoid modification during iteration
            try:
                callback(event)
            except Exception as e:
                logging.error(f"Error in customer callback for {event}: {e}")
    
    def _on_renderer_reloaded(self, batch: list[LifeCycleEvent]) -> None:
        """
        Customer callback for renderer hot reload events.
        
        This is called by the RendererRegistry when a renderer class is reloaded, added, or removed.
        It clears the cache for affected renderers.
        
        Args:
            event: The hot reload event with complete context
        """
        # Forward to all individual event listeners
        for event in batch:
            logging.info(
                f"NodeRenderFactory: Node {event.event_type.value} - {event.registry_key} "
                f"from library '{event.library_identity.label}'"
            )
            # Clear cache for affected renderer
            if event.registry_key in self._renderer_cache:
                logging.debug(f"Clearing renderer cache for: {event.registry_key}")
                del self._renderer_cache[event.registry_key]
        
            # Notify customers (UINodes) about the renderer reload
            self._notify_subscribers(event)
 
    def _on_widget_reloaded(self, batch: list[LifeCycleEvent]) -> None:
        """
        Customer callback for widget hot reload events.
        
        This is called by the WidgetRegistry when a widget class is reloaded, added, or removed.
        Since widgets can be used by any renderer, we clear the entire cache.
        
        Args:
            event: The hot reload event with complete context
        """
        # Forward to all individual event listeners
        for event in batch:
            logging.info(
                f"NodeRenderFactory: Widget {event.event_type.value} - {event.registry_key} "
                f"from library '{event.library_identity.label}'"
            )
        
        # Clear entire renderer cache since widgets can affect any renderer
        logging.debug("Clearing entire renderer cache due to widget reload")
        self._renderer_cache.clear()
        
        # Note: We don't notify customers for widget reloads as renderers handle this internally
