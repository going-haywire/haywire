"""
NodeRenderFactory - Factory for creating UINodeCard instances using NodeRenderer classes

This factory manages cached NodeRenderer instances and provides the generate_node method
that looks up renderers from the renderers registry.

Enhanced with customer notification system for UINode hot reload support.
"""

import logging
from typing import Any, Callable, Dict, Type, List

from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LiveCycleBatchCallback
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.ui.errors.error_info import error_render_detail, render_error_info
from haywire.ui.ui_nodecard import UINodeCard

from ..widget.factory import WidgetFactory
from ..widget.registry import WidgetRegistry
from .base import BaseRenderer
from .registry import RendererRegistry


FactoryEventCallback = Callable[[str], None] # Function signature for factory event callbacks

NO_RENDERER_DEFINED: str = "no.renderer.defined"

class RenderFactory():
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

        self._widget_factory = WidgetFactory(widget_registry)

        # Subscribe to widget factory lifecycle events
        self._widget_factory.add_widget_lifecycle_subscriber(self._listen_on_widget_lifecycle_events)

        # Subscribe to renderer registry lifecycle events
        self._renderer_registry.add_batch_event_subscriber(self._listen_on_renderer_lifecycle_event)
        
        # Cache for BaseRenderer instances by registry key
        self._renderer_cache: Dict[str, BaseRenderer] = {}
        
        # Customer callbacks for factory hot reload notifications
        # mapping from node_id key to callback function
        self._nodeid_to_factory_subscriber: dict[str, FactoryEventCallback] = {}

        # Mapping from renderer registry key to the wrapper node id that uses that renderer
        self._renderer_regkey_to_node_id: dict[str, set[str]] = {}

        # Mapping from node id to the renderer registry key it uses
        # this is used to help cleaning up the _renderer_regkey_to_node_id mapping
        self._nodeid_to_renderer_regkey: dict[str, str] = {}
    
    # this method is called by UINode to render the node
    def render(self, renderer_registry_key: str | None, wrapper: NodeWrapper, _is_error_render: bool = False) -> UINodeCard | None:
        """Render a node with the renderer with the renderer_registry_key.

        If no renderer_registry_key is provided, the default renderer set by
        the renderer registry is used.
                
        Args:
            renderer_registry_key: The registry key of the renderer to use
            wrapper: NodeWrapper instance containing node information
            
        Returns:
            UINodeCard instance or None if rendering failed
        """                
        if renderer_registry_key is None:
            # this can happen if :
            # the node has no renderer assigned AND the registry has no default renderer available
            renderer_registry_key = NO_RENDERER_DEFINED  # Fallback if no default renderer is set"

        ui_nodeCard: UINodeCard | None = None

        renderer_instance: BaseRenderer | None = None

        try:
            # if the node is undefined, we throw an error that should be caught with the error renderer
            if renderer_registry_key is NO_RENDERER_DEFINED:
                raise HaywireException(
                    category="Renderer Lookup Error",
                    operation="renderer_lookup",
                    message=f"No renderer registry key provided and no default renderer has been set in the renderer registry.",
                    suggestions=[
                        "1. Provide a valid renderer registry key",
                        "2. Set a default renderer for the registry",
                        "3. Check if the default renderer has failed to load"
                    ]
                ).log()

            if renderer_registry_key in self._renderer_cache:
                renderer_instance = self._renderer_cache[renderer_registry_key]
            else:            
                renderer_instance = self.get_renderer(renderer_registry_key)

            ui_nodeCard = renderer_instance._render(wrapper=wrapper)

            # once the renderer instance is successfully used, cache it
            self._renderer_cache[renderer_registry_key] = renderer_instance
                
        except Exception as error:
            logging.error(f"Failed to use renderer '{renderer_registry_key}' for node '{wrapper.node.identity.label}' with node id '{wrapper.node_id}'", exc_info=True)
            if not isinstance(error, HaywireException):
                error = HaywireException.from_exception(
                    exception=error,
                    category="Render Error",
                    operation="renderer_lookup",
                    message=f"Failed to use renderer '{renderer_registry_key}' for node '{wrapper.node.identity.label}' with node id '{wrapper.node_id}'"
                ).enrich(
                    library_identity=renderer_instance.__class__.class_library if renderer_instance else None,
                    registry_key=renderer_registry_key
                )
            

            wrapper.state.error = error
            error_renderer_registry_key = self._renderer_registry.get_error_renderer_registry_key()

            if _is_error_render:
                # Prevent infinite recursion. If there is something wrong with the error node,
                # we cannot recover from this.
                
                error_render_detail(error)

                return None

            # render error 
            ui_nodeCard = self.render(
                    renderer_registry_key=error_renderer_registry_key, 
                    wrapper=wrapper, 
                    _is_error_render=True
                )
            
            # if we reach this point, we just returned from an error render that was executed 
            # because of a render error in the intended/default renderer. ui_nodeCard can be None
            # if the error renderer also failed, but in is hasn't - we have widgets to track..
        
        if ui_nodeCard:
            # Map renderer registry key to node ID for hot reload tracking
            # this might not be the key of the renderer that actually gets used due to fallback
            # to an error renderer, but its the one we are interested in for hot reloads

            # cleanup previous mappings if any
            if wrapper.node_id in self._nodeid_to_renderer_regkey:
                previous_regkey = self._nodeid_to_renderer_regkey[wrapper.node_id]
                if wrapper.node_id in self._renderer_regkey_to_node_id.get(previous_regkey, set()):
                    self._renderer_regkey_to_node_id[previous_regkey].remove(wrapper.node_id)
            
            if _is_error_render == False:
                # this makes sure we only track the intended renderer, not the error renderer

                # one to many mapping
                self._renderer_regkey_to_node_id.setdefault(renderer_registry_key, set()).add(wrapper.node_id)
                # one to one mapping
                self._nodeid_to_renderer_regkey[wrapper.node_id] = renderer_registry_key

        return ui_nodeCard

    def get_renderer(self, registry_key: str) -> BaseRenderer:
        """
        Get a renderer instance for the given element using the renderer registry.
        Args:
            registry_key: The registry key to get the renderer for
        Returns:
            BaseRenderer: The instantiated renderer for the registry key
        """
 
        lc_event = self._renderer_registry.get_renderer_event(registry_key)

        renderer_cls: type[BaseRenderer] | None = lc_event.affected_class

        renderer_instance = None

        if renderer_cls is not None:
            try:
                renderer_instance = renderer_cls(self._widget_factory)

                self._renderer_cache[registry_key] = renderer_instance

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
        
    def add_factory_lifecycle_subscriber(self, node_id: str, callback: FactoryEventCallback) -> None:
        """
        Register a customer callback for factory event notifications.
        
        Callbacks are invoked when either
        - a renderer is hot-reloaded, added, or removed.
        - a widget is hot-reloaded, added, or removed.
        
        Args:
            node_id: The ID of the node to associate with the callback
            callback: Function with signature FactoryEventCallback
        """
        self._nodeid_to_factory_subscriber[node_id] = callback

    
    def remove_factory_lifecycle_subscriber(self, node_id: str) -> None:
        """
        Unregister a customer callback.
        
        Args:
            node_id: The ID of the node associated with the callback
        """
        if node_id in self._nodeid_to_factory_subscriber:
            del self._nodeid_to_factory_subscriber[node_id]
        
        self._unregister_node(node_id)

    def _notify_factory_subscribers(self, node_id: str) -> None:
        """
        Notify all subscribers about lifecycle events affected
        by changes of renderer and widgets the factory has detected.
        
        Args:
            node_id: The ID of the node affected by the lifecycle event
        """
        if node_id in self._nodeid_to_factory_subscriber:
            callback = self._nodeid_to_factory_subscriber[node_id]
            callback(node_id)
    
    def _listen_on_renderer_lifecycle_event(self, batch: list[LifeCycleEvent]) -> None:
        """
        Listener for renderer hot reload events is called by the RendererRegistry 
        when a renderer class is reloaded, added, or removed.
        It clears the cache for affected renderers.
        
        Args:
            event: The hot reload event with complete context
        """
        # Forward to all individual event listeners
        for event in batch:
            if event.registry_key:
                logging.info(
                    f"NodeRenderFactory: Node {event.event_type.value} - {event.registry_key} "
                    f"from library '{event.library_identity.label}'"
                )
                # Clear cache for affected renderer
                if event.registry_key in self._renderer_cache:
                    del self._renderer_cache[event.registry_key]
                else:
                    # in this case the renderer has never been used/cached before.
                    # if nodes have been rendering with a non existing renderer 
                    # (most likely the error renderer), they might be interested to 
                    # now about that new renderer and should be informed
                    node_ids = set(self._renderer_regkey_to_node_id.get(NO_RENDERER_DEFINED, set()))
                    for node_id in node_ids:
                        self._notify_factory_subscribers(node_id)
            
                # Notify customers (UINodes) about the renderer reload
                reg_key = event.registry_key
                node_ids = set(self._renderer_regkey_to_node_id.get(reg_key, set()))
                for node_id in node_ids:
                    self._notify_factory_subscribers(node_id)

    def _listen_on_widget_lifecycle_events(self, node_ids: set[str]):
        """
        Listener for widget lifecycle events emited by the widget factory

        it directly forwards the affected node IDs to the factory subscribers.
        
        Args:
            node_ids: Set of node IDs affected by the widget lifecycle event
        """
        for node_id in node_ids:
            self._notify_factory_subscribers(node_id)
        
    def _unregister_node(self, node_id: str):
        """
        Remove node ID tracking from both renderer and widget factories 
        when node is destroyed.
        Args:
            node_id: The node ID to unregister
        """
        reg_key = self._nodeid_to_renderer_regkey.get(node_id, None)
        if reg_key:
            if self._renderer_regkey_to_node_id[reg_key]:
                if node_id in self._renderer_regkey_to_node_id[reg_key]:
                    self._renderer_regkey_to_node_id[reg_key].remove(node_id)
            del self._nodeid_to_renderer_regkey[node_id]
        self._widget_factory.unregister_widget_for_node(node_id)

    def reset_cache(self):
        """Clear all cached renderer instances."""
        self._renderer_cache.clear()

    def cleanup(self):
        """Cleanup resources and unregister from registries."""
        self._renderer_registry.remove_batch_event_subscriber(self._listen_on_renderer_lifecycle_event)
        self._widget_factory.remove_widget_lifecycle_subscriber(self._listen_on_widget_lifecycle_events)
        self._widget_factory.cleanup()
        self._nodeid_to_factory_subscriber.clear()
        self._renderer_cache.clear()