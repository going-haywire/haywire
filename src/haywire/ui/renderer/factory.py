"""
NodeRenderFactory - Factory for creating UINodeCard instances using NodeRenderer classes

This factory manages cached NodeRenderer instances and provides the generate_node method
that looks up renderers from the renderers registry.

Enhanced with customer notification system for UINode hot reload support.
"""

import logging
from typing import Any, Callable, Dict, Type, List

from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.node.dataclasses import NodeErrorInfo
from haywire.core.types.ports import PortInlet
from haywire.core.ui.widget.registry import WidgetRegistry
from haywire.core.ui.renderer.registry import RendererRegistry
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LiveCycleBatchCallback
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.ui.renderer.base import IBaseRenderer, IRenderFactory, UINodeCard
from haywire.ui.errors.error_info import error_render_detail, render_error_info
from haywire.ui.renderer.widget_factory import WidgetFactory
from haywire.ui.ui_nodecard import NiceUINodeCard


RendererCallback = Callable[[], None]

class RenderFactory(IRenderFactory):
    """
    Factory class for creating UINodeCard instances using NodeRenderer classes.
    
    This factory:
    - Has access to both renderers registry and widgets registry
    - Caches stateless NodeRenderer instances for reuse
    - Provides generate_node method for creating UINodeCard instances
    - Notifies customers (UINodes) when renderers are hot-reloaded
    """
    
    def __init__(self, renderer_registry: RendererRegistry, widget_registry: WidgetRegistry):
        """
        Initialize the factory with registries.
        
        Args:
            renderers_registry: Registry for NodeRenderer classes
            widget_registry: Registry for widget classes (passed to NodeRenderer)
        """
        self._renderer_registry: RendererRegistry = renderer_registry

        self.widget_factory = WidgetFactory(widget_registry)

        self.widget_factory.add_widget_lifecycle_subscriber(self._nodeids_updated_by_widget)
        
        # Cache for NodeRenderer instances (stateless, so can be reused)
        self._renderer_cache: Dict[str, IBaseRenderer] = {}
        
        # Customer callbacks for hot reload notifications
        # mapping from registry key to callback function
        self._renderer_lifecycle_subscribers: List[RendererCallback] = []

        self._nodeid_to_renderer_regkey: dict[str, str] = {}
        
        # Register for hot reload notifications from registries
        self._renderer_registry.add_batch_event_subscriber(self._on_renderer_reloaded)
    
    def generate_node(self, renderer_registry_key: str | None, wrapper: NodeWrapper) -> NiceUINodeCard | None:
        """Render a widget for the given inlet and return the widget instance.
        
        Note: The UI element is automatically added to the current NiceGUI context.
        
        Args:
            inlet: The inlet port to render a widget for
            node_id: ID of the node containing this inlet
            
        Returns:
            BaseWidget instance or None if widget creation failed
        """        
        if renderer_registry_key is None:
            renderer_registry_key = self._renderer_registry.get_default_renderer_registry_key()

        ui_nodeCard: UINodeCard | None = None

        try:
            
            renderer_instance = self.get_renderer(renderer_registry_key)

            ui_nodeCard = renderer_instance._render(wrapper=wrapper)
                
        except Exception as error:
            logging.error(f"Failed to render node '{wrapper.node.identity.label}  with node id '{wrapper.node_id}': {error}", exc_info=True)
            if not isinstance(error, HaywireException):
                error = HaywireException.from_exception(
                    exception=error,
                    category="Renderer Render Error",
                    operation="renderer_lookup",
                    message=f"Failed to use renderer '{renderer_registry_key}' for node '{wrapper.node.identity.label}' with node id '{wrapper.node_id}'"
                ).enrich(
                    library_identity=renderer_instance.__class__.class_library if renderer_instance else None,
                    registry_key=renderer_registry_key
                ).log()
            

            wrapper.state.error = error

            error_renderer_registry_key = 'unknown'

            try:
                # get the error widget class from the registry
                renderer_cls = self._renderer_registry.get_error_renderer()

                if renderer_cls:
                    error_renderer_registry_key = renderer_cls.class_identity.registry_key
                renderer_instance = renderer_cls(self)

                ui_nodeCard = renderer_instance._render(wrapper=wrapper)

            except Exception as e:
                # Fallback to error display if widget creation fails completely
                logging.error(f"Failed to create error renderer '{error_renderer_registry_key}' for node '{wrapper.node_id}': {e}", exc_info=True)

                error_render_detail(error)

        # Map node ID to renderer registry key for hot reload tracking
        # this might not be the key of the renderer that actually gets used due to fallback
        self._nodeid_to_renderer_regkey[wrapper.node_id] = renderer_registry_key

        return ui_nodeCard

    def get_renderer(self, registry_key: str) -> IBaseRenderer:
        """
        Get a renderer instance for the given element using the renderer registry.
        Args:
            registry_key: The registry key to get the renderer for
        Returns:
            BaseRenderer: The instantiated renderer for the registry key
        """
 
        lc_event = self._renderer_registry.get_renderer_event(registry_key)

        renderer_cls: type[IBaseRenderer] | None = lc_event.affected_class

        renderer_instance = None

        if renderer_cls is not None:
            try:
                renderer_instance = renderer_cls(self)
            except Exception as e:
                # Create detailed error with context about the node instantiation
                error = HaywireException.from_exception(
                    exception=e,
                    category="Renderer Instantiation Error",
                    operation="renderer_lookup",
                    message=f"Failed to instantiate renderer '{registry_key}'"
                ).enrich(
                    registry_key=registry_key,
                    module_name=lc_event.module_name,
                    library_identity=lc_event.library_identity
                )

                raise error
        return renderer_instance
        
    def add_renderer_lifecycle_subscriber(self, callback: RendererCallback) -> None:
        """
        Register a customer callback for renderer hot reload notifications.
        
        Callbacks are invoked when a renderer is hot-reloaded, added, or removed.
        
        Args:
            callback: Function with signature (event: list[LifeCycleEvent]) -> None
        """
        if callback not in self._renderer_lifecycle_subscribers:
            self._renderer_lifecycle_subscribers.append(callback)
            logging.debug(f"Added customer callback to NodeRenderFactory: {callback}")
    
    def remove_renderer_lifecycle_subscriber(self, callback: RendererCallback) -> None:
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


    def _nodeids_updated_by_widget(self, node_ids: set[str]):
        """Handle widget lifecycle events and notify subscribers of affected node IDs."""
        node_ids_affected: set[str] = set()

        for event in event.events:
            # find all node IDs associated with this widget registry key
            if event.registry_key not in self._widget_regkey_to_nodeids:
                continue

            # add all associated node IDs to the affected set

    def _nodeids_updated_by_widget(self, node_ids: set[str]):
        """Handle widget lifecycle events and notify subscribers of affected node IDs."""
        # The node_ids parameter already contains the affected node IDs from WidgetFactory
        # Now we need to find which renderers are affected and notify subscribers
        
        for node_id in node_ids:
            if node_id in self._nodeid_to_renderer_regkey:
                renderer_key = self._nodeid_to_renderer_regkey[node_id]
                # Get the lifecycle event for this renderer
                try:
                    event = self._renderer_registry.get_renderer_event(renderer_key)
                    self._notify_subscribers(event)
                except Exception as e:
                    logging.warning(f"Could not get renderer event for node {node_id}: {e}")

    def unregister_node(self, node_id: str):
        """
        Remove node ID tracking from both renderer and widget factories 
        when node is destroyed.
        Args:
            node_id: The node ID to unregister
        """
        if node_id in self._nodeid_to_renderer_regkey:
            del self._nodeid_to_renderer_regkey[node_id]
        self.widget_factory.unregister_widget_for_node(node_id)

    def cleanup(self):
        """Cleanup resources and unregister from registries."""
        self._renderer_registry.remove_batch_event_subscriber(self._on_renderer_reloaded)
        self.widget_factory.remove_widget_lifecycle_subscriber(self._nodeids_updated_by_widget)
        self.widget_factory.cleanup()
        self._renderer_lifecycle_subscribers.clear()
        self._renderer_cache.clear()