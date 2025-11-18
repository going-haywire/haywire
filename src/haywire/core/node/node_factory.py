"""
Pure Node Factory utility.

This factory is a utility class that creates node instances from registry keys.
It handles hot reloading support and node tracking but does not manage graph
lifecycle or undo operations - those are handled by Graph and Actions respectively.
"""

import time
import uuid
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from collections import defaultdict


if TYPE_CHECKING:
    from ..graph.graph import HaywireGraph

from .base_node import BaseNode, node
from .node_wrapper import NodeWrapper
from ..library.registries.reg_node import NodeRegistry
from ..library.library_identity import LibraryIdentity
from ..library.hot_reload_event import LifeCycleEvent, LifeCycleEventType, LiveCycleBatchCallback, LiveCycleEventCallback
from ..errors import log_detailed_error


# ============================================================================ 
#    THIS NODE SHOULD NEVER BE USED FOR INHERITANCE
#    IT IS THE MOST BASIC NODE THAT SHOULD RUN WITH THE LEAST DEPENDENCIES
#    IT IS USED AS A FALLBACK BY THE NODE FACTORY
#    WHEN NO OTHER NODE CAN BE LOADED
# ============================================================================ 

# TODO: Write Test for SkeletonNode. 
# This node should always work and be instantiable, including to load arbitray node serializations.

@node(
    label='Skeleton Node',
    description='A minimal node implementation for fallback purposes',
    search_tags=[],
    menu=''
)
class __SkeletonNode__(BaseNode):
    """    
    THIS NODE SHOULD NEVER BE USED FOR INHEITANCE
    IT IS THE MOST BASIC NODE THAT SHOULD RUN WITH THE LEAST DEPENDENCIES
    IT IS USED AS A FALLBACK WHEN NO OTHER NODE CAN BE LOADED
    """

    def worker(self, context: dict) -> dict | None:
        """No-op worker"""
        return None


class NodeFactory:
    """
    Pure node factory utility.
    
    This factory is a utility class that creates node instances from registry keys.
    It handles hot reload tracking but does not manage graph lifecycle or undo 
    operations - those are handled by Graph and Actions respectively.
    """
    
    def __init__(self, node_registry: NodeRegistry):
        """
        Initialize the node factory.
        
        Args:
            node_registry: Registry containing node class definitions
        """
        self.node_registry = node_registry
                
        # batch notification callbacks
        self._livecycle_batch_subscribers: List[LiveCycleBatchCallback] = []

        # individual event notification callbacks
        self._livecycle_event_subscribers: Dict[str, List[LiveCycleEventCallback]] = {} # registry_key -> list of callbacks
        
        # Register this factory for livecycle events from node registry hot reloads
        self.node_registry.add_batch_event_subscriber(self._listen_on_livecycle_event)
        
    def get_node_event(self, registry_key: str) -> LifeCycleEvent:
        """
        Get the node class for a given registry key.
        
        Args:
            registry_key: The registry key of the node to retrieve
        Returns:
            LifeCycleEvent: The lifecycle event for the requested node
        """
        return self.node_registry.get_node_event(registry_key)

    def get_error_node(self) -> BaseNode:
        """
        Get the registered error node class, or fallback.
        
        Returns:
            The error node class or __SkeletonNode__ if not registered
        """
        node_cls = self.node_registry._get_error_node()
        if node_cls is None:
            node_cls = __SkeletonNode__
        return node_cls
    
    
    def _listen_on_livecycle_event(self, batch: list[LifeCycleEvent]) -> None:
        """
        listener for node livecycle changes from registry
        
        This is called by the NodeRegistry when a node class is reloaded, added, or removed.
        It forwards the notification to all registered hot reload listeners (typically NodeWrappers).
        
        Args:
            batch: The batch of events with complete context
        """        
        # Forward to all livecycle batch listeners (Context Menu, etc.)
        for listener in self._livecycle_batch_subscribers[:]:
            listener(batch)

        # Forward to all individual event listeners
        for event in batch:
            logging.info(
                f"NodeFactory: Node {event.event_type.value} - {event.registry_key} "
                f"from library '{event.library_identity.label}'"
            )
            if event.registry_key in self._livecycle_event_subscribers:
                callbacks = self._livecycle_event_subscribers[event.registry_key]
                for callback in callbacks:
                    callback(event)
    
    ############################################################
    #
    #        Public API for livecycle event listeners
    #
    ############################################################

    def add_batch_listener(self, callback: LiveCycleBatchCallback) -> None:
        """
        Add a callback for batch notifications.
        
        Args:
            callback: Function called with Batches of LifeCycleEvents
        """
        self._livecycle_batch_subscribers.append(callback)
    
    def remove_batch_listener(self, callback: LiveCycleBatchCallback) -> None:
        """
        Remove a batch notification callback.
        
        Args:
            callback: The callback to remove
        """
        if callback in self._livecycle_batch_subscribers:
            self._livecycle_batch_subscribers.remove(callback)
    
    def add_event_subscriber(self, registry_key: str, callback: LiveCycleEventCallback) -> None:
        """
        Add a callback for event of specific registry_key.
        
        Args:
            registry_key: The registry key to listen for
            callback: Function called with LiveCycleEvent
        """
        if registry_key not in self._livecycle_event_subscribers:
            self._livecycle_event_subscribers[registry_key] = []
        self._livecycle_event_subscribers[registry_key].append(callback)

    def remove_event_subscriber(self, registry_key: str, callback: LiveCycleEventCallback) -> None:
        """
        Remove a callback for event of specific registry_key.
        
        Args:
            registry_key: The registry key to stop listening for
            callback: The callback to remove
        """
        if registry_key in self._livecycle_event_subscribers:
            if callback in self._livecycle_event_subscribers[registry_key]:
                self._livecycle_event_subscribers[registry_key].remove(callback)
                if not self._livecycle_event_subscribers[registry_key]:
                    del self._livecycle_event_subscribers[registry_key]
                
    
    # ============================================================================
    # Node Discovery and UI Services 
    # ============================================================================
    
    def get_menu_structure(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get nodes organized by menu path for UI building.

        Returns:
            Dictionary mapping menu paths to lists of node info dicts
        """
        menu = {}

        for key in self.node_registry.list_names():
            node_class = self.node_registry.get(key)
            
            # Use class_identity if available, fallback to old attributes
            if hasattr(node_class, 'class_identity'):
                identity = node_class.class_identity
                menu_path = identity.menu
                label = identity.label
                description = identity.description
                tags = identity.search_tags
            else:
                menu_path = getattr(node_class, 'node_menu', 'misc')
                label = node_class.class_library.label
                description = node_class.class_library.description
                tags = getattr(node_class, 'node_search_tags', [])

            if menu_path not in menu:
                menu[menu_path] = []

            menu[menu_path].append({
                'label': label,           # Display name
                'key': key,               # Registry key
                'description': description,
                'tags': tags
            })

        return menu

    def search_nodes(self, query: str) -> List[Dict[str, str]]:
        """
        Search for nodes matching a query string.

        Args:
            query: Search query string

        Returns:
            List of matching node info dicts
        """
        results = []
        query_lower = query.lower()

        for key in self.node_registry.list_names():
            node_class = self.node_registry.get(key)

            # Use class_identity if available, fallback to old attributes
            if hasattr(node_class, 'class_identity'):
                identity = node_class.class_identity
                label = identity.label
                description = identity.description
                tags = identity.search_tags

            # Search in label, description, and tags
            searchable = [
                label.lower(),
                description.lower(),
                *[tag.lower() for tag in tags]
            ]

            if any(query_lower in text for text in searchable):
                library = node_class.class_library
                library_label = library.label if library else 'Unknown'

                results.append({
                    'label': label,
                    'key': key,
                    'description': description,
                    'library': library_label
                })

        return results

    def list_all_nodes(self) -> List[str]:
        """
        Get list of all registered node registry keys.

        Returns:
            List of all registry keys
        """
        return self.node_registry.list_names()

    def get_node_info(self, registry_key: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific node.

        Args:
            registry_key: Registry key of the node

        Returns:
            Dictionary with node information or None if not found
        """

        node_class = self.node_registry.get(registry_key)
        if node_class is not None:
            library_identity = node_class.class_library
            
            # Use class_identity if available, fallback to old attributes
            if hasattr(node_class, 'class_identity'):
                identity = node_class.class_identity
                label = identity.label
                description = identity.description
                tags = identity.search_tags
                menu = identity.menu
            else:
                label = node_class.class_library.label
                description = node_class.class_library.description
                tags = getattr(node_class, 'node_search_tags', [])
                menu = getattr(node_class, 'node_menu', 'misc')
            
            return {
                'registry_key': registry_key,
                'label': label,
                'description': description,
                'search_tags': tags,
                'menu': menu,
                'library_label': library_identity.label if library_identity else None,
                'library_version': library_identity.version if library_identity else None,
                'class_name': node_class.__name__,
                'module': node_class.__module__
            }
        
        return None
