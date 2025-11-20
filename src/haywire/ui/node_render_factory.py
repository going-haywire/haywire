"""
NodeRenderFactory - Factory for creating UINodeCard instances using NodeRenderer classes

This factory manages cached NodeRenderer instances and provides the generate_node method
that looks up renderers from the renderers registry.

Enhanced with customer notification system for UINode hot reload support.
"""

import logging
from typing import Any, Dict, Type, List, Callable

from nicegui.element import Element

from haywire.core.errors.utils import log_detailed_error
from haywire.core.node.base_node import BaseNode
from haywire.core.library.registries.reg_widget import WidgetRegistry
from haywire.core.library.registries.reg_renderer import RendererRegistry
from haywire.core.library.library_identity import LibraryIdentity
from haywire.core.library.hot_reload_event import LifeCycleEvent, LifeCycleEventType, LiveCycleBatchCallback
from haywire.core.node.dataclasses import NodeErrorInfo
from haywire.core.types.ports import DataPort, PortInlet
from haywire.core.ui.base_renderer import BaseNodeRenderer
from haywire.core.ui.base import UINodeCard
from haywire.core.ui.base_widget import BaseWidget
from haywire.ui.error_widget import ErrorWidget
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
    
    def generate_node(self, renderer_registry_key: str | None, node: BaseNode) -> tuple[UINodeCard, str]:
        """
        Generate a UINodeCard for the given node using the specified renderer.
        
        Args:
            renderer_registry_key: Name of the renderer to use (None for default)
            node: The HaywireNode to render
            
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
        return renderer_instance._render(node)
    
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

    def render_widget(self, inlet: PortInlet, node_id: str) -> Element:
        """Render a widget for the given inlet."""        
        ui_element: Element

        try:
            widget = self.get_widget(inlet)
            ui_element = widget.render()            
        except Exception as e:
            error = log_detailed_error(
                exception=e,
                operation="Widget creation",
                registry_key=inlet.widget,
                message=str(e)
            )
            # Fallback to error display if widget creation fails
            creationerror = NodeErrorInfo(
                error='Widget Creation Error',
                error_message=str(e)
            )
            creationerror.add_note(f"Element: {inlet.id}")
            creationerror.add_note(f"Requested widget: {getattr(inlet, 'widget', 'None')}")

            ui_element = render_error_info(creationerror)
    
        return ui_element

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

        widget_instance: BaseWidget | None = None

        event = lc_event

        if widget_cls is not None:
            try:
                widget_instance = widget_cls(element, lc_event.error)
            except Exception as e:
                # Create detailed error with context about the node instantiation
                error = log_detailed_error(
                    exception=e,
                    operation="Instantiate Node",
                    module_name=event.module_name,
                    registry_key=key,
                    class_name=widget_cls.__name__,
                    library_identity=event.library_identity,
                    message=f"Failed to instantiate widget '{key}'"
                )
                event = lc_event.create_derived_event(
                    error=error,
                    error_info=f"Widget instantiation failed: {str(e)}",
                    affected_class=widget_cls,
                    event_type=LifeCycleEventType.CLASS_INSTANTIATION_FAILED
                    )
                
                widget_cls = ErrorWidget

                try:
                    widget_instance = widget_cls(element, error)   
                except Exception as e2:
                    # Last resort: log and raise
                    error = log_detailed_error(
                        exception=e2,
                        operation="Instantiate Error Widget",
                        module_name=lc_event.module_name,
                        registry_key=key,
                        class_name=widget_cls.__name__,
                        library_identity=lc_event.library_identity,
                        message=f"Failed to instantiate error widget '{key}'"
                    )
                    event = lc_event.create_derived_event(
                        error=error,
                        error_info=f"Error widget instantiation failed: {str(e)}",
                        affected_class=None,
                        event_type=LifeCycleEventType.CLASS_INSTANTIATION_FAILED
                    )
                    widget_instance = None        

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
