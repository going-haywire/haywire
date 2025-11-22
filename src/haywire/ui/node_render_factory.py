"""
NodeRenderFactory - Factory for creating UINodeCard instances using NodeRenderer classes

This factory manages cached NodeRenderer instances and provides the generate_node method
that looks up renderers from the renderers registry.

Enhanced with customer notification system for UINode hot reload support.
"""

import logging
from typing import Any, Dict, Type, List, Callable

from nicegui.element import Element

from haywire.core.errors import HaywireException
from haywire.core.node.base_node import BaseNode
from haywire.core.library.registries.reg_widget import WidgetRegistry
from haywire.core.library.registries.reg_renderer import RendererRegistry
from haywire.core.library.library_identity import LibraryIdentity
from haywire.core.library.hot_reload_event import LifeCycleEvent, LifeCycleEventType, LiveCycleBatchCallback
from haywire.core.node.dataclasses import NodeErrorInfo
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types.ports import DataPort, PortInlet
from haywire.core.ui.base_renderer import BaseNodeRenderer
from haywire.core.ui.base import UINodeCard
from haywire.core.ui.base_widget import BaseWidget
from haywire.ui.utils import render_error_info

class NodeRenderFactory:
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
        self._renderer_cache: Dict[str, BaseNodeRenderer] = {}
        
        # Customer callbacks for hot reload notifications
        self._renderer_lifecycle_subscribers: List[LiveCycleBatchCallback] = []
        
        # Register for hot reload notifications from registries
        self.renderers_registry.add_batch_event_subscriber(self._on_renderer_reloaded)
        self.widget_registry.add_batch_event_subscriber(self._on_widget_reloaded)
    
    def generate_node(self, renderer_registry_key: str | None, wrapper: NodeWrapper) -> tuple[UINodeCard, str]:
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
        return renderer_instance._render(wrapper)
    
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

    def render_widget(self, inlet: PortInlet, node_id: str) -> BaseWidget | None:
        """Render a widget for the given inlet and return the widget instance.
        
        Note: The UI element is automatically added to the current NiceGUI context.
        
        Args:
            inlet: The inlet port to render a widget for
            node_id: ID of the node containing this inlet
            
        Returns:
            BaseWidget instance or None if widget creation failed
        """        
        widget_instance: BaseWidget | None = None

        try:
            widget_instance = self.get_widget(inlet)
            ui_element = widget_instance.render()
            
            # Apply styling to the UI element if possible
            if hasattr(ui_element, 'classes') and callable(ui_element.classes):
                ui_element.classes('widget-container zoom-pan-lod2')
                
        except Exception as error:
            logging.error(f"Failed to render widget '{inlet.widget}' for inlet '{inlet.id}' in node '{node_id}': {error}", exc_info=True)
            if not isinstance(error, HaywireException):
                error = HaywireException.from_exception(
                    exception=error,
                    category="Widget Render Error",
                    operation="widget_lookup",
                    message=f"Failed to render widget '{inlet.widget}' for inlet '{inlet.id}' in node '{node_id}'"
                ).enrich(
                    registry_key=inlet.widget
                ).log()
            error_widget_registry_key = 'unkwown'
            try:
                widget_cls = self.widget_registry._get_error_widget()
                if widget_cls:
                    error_widget_registry_key = widget_cls.class_identity.registry_key
                widget_instance = widget_cls(inlet, error)
                ui_element = widget_instance.render()
            except Exception as e:
                # Fallback to error display if widget creation fails completely
                logging.error(f"Failed to create error widget '{error_widget_registry_key}' for inlet '{inlet.id}' in node '{node_id}': {e}", exc_info=True)

                creationerror = NodeErrorInfo(
                    error='Fatal Error',
                    error_message=str(e)
                )
                creationerror.add_note(f"Check log for details")
                creationerror.add_note(f"Element: {inlet.id}")
                creationerror.add_note(f"Requested widget: {getattr(inlet, 'widget', 'None')}")

                render_error_info(creationerror)
                
                widget_instance = None
    
        return widget_instance

    def get_widget(self, element: DataPort) -> BaseWidget:
        """
        Get a widget instance for the given element using the widget registry.
        Args:
            element: The DataPort (inlet or outlet) to get the widget for
        Returns:
            BaseWidget: The instantiated widget for the element
        """
 
        key = element.widget

        lc_event = self.widget_registry.get_widget_event(key)

        widget_cls = lc_event.affected_class

        widget_instance = None

        if widget_cls is not None:
            try:
                widget_instance = widget_cls(element, lc_event.error)
            except Exception as e:
                # Create detailed error with context about the node instantiation
                error = HaywireException.from_exception(
                    exception=e,
                    category="Widget Instantiation Error",
                    operation="widget_lookup",
                    message=f"Failed to instantiate widget '{key}'"
                ).enrich(
                    registry_key=key,
                    module_name=lc_event.module_name,
                    library_identity=lc_event.library_identity
                )

                raise error

        return widget_instance
 
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
