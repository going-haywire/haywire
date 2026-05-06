"""
Pure Node Factory utility.

This factory is a utility class that creates node instances from registry keys.
It handles hot reloading support and node tracking but does not manage graph
lifecycle or undo operations - those are handled by Graph and Actions respectively.
"""

import logging
from typing import Dict, List, Optional

from haywire.core.errors.haywire_exception import HaywireException
from . import BaseNode, NodeRegistry
from .info import NodeInfo

from ..registry.lifecycle_event import LifeCycleEvent, LifeCycleBatchCallback, LifeCycleEventCallback

logger = logging.getLogger(__name__)


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
        self._lifecycle_batch_subscribers: List[LifeCycleBatchCallback] = []

        # individual event notification callbacks
        # registry_key -> list of callbacks
        self._lifecycle_event_subscribers: Dict[str, List[LifeCycleEventCallback]] = {}

        # Register this factory for lifecycle events from node registry hot reloads
        self.node_registry.add_batch_event_subscriber(self._listen_on_lifecycle_event)

    def get_alternate_node_registry_keys(self, registry_key: str) -> list[str]:
        """
        Get alternate node registry keys for a given registry key.

        Args:
            registry_key: The registry key of the node to find alternates for
        Returns:
            List of alternate registry keys
        """
        alternates = self.node_registry.get_alternate_node_registry_keys(registry_key)
        return alternates

    def get_node(self, registry_key: str) -> tuple[type[BaseNode], HaywireException | None]:
        """
        Get the node class for a given registry key.

        Fallback chain:
            1. The actual class from a successful registry event.
            2. The registered error node (registries/applications register one).

        Args:
            registry_key: The registry key of the node to retrieve

        Returns:
            (node_cls, node_error): The class to instantiate and an optional
            error describing why the requested class wasn't returned directly.

        Raises:
            HaywireException: If neither the requested class nor an error node
                is available — this is a setup error (no error node registered).
        """
        node_cls: type[BaseNode] | None = None
        node_error: HaywireException | None = None
        node_event = self.node_registry.get_node_lastevent(registry_key)
        if node_event:
            node_cls = node_event.affected_class
            if not node_event.is_successful_event():
                node_error = node_event.error
        else:
            node_error = HaywireException(
                message=f"Node with registry key '{registry_key}' not found in registry.",
                operation="Node Lookup",
                registry_key=registry_key,
                category="NodeNotFoundError",
                suggestions=[
                    "Ensure the node's library is correctly installed and loaded.",
                    "Check for typos in the registry key.",
                    "Verify that the node class is properly decorated with @node.",
                ],
            )

        # Fall back to registered error node if no concrete class available.
        if node_cls is None:
            node_cls = self.node_registry._get_error_node()
        if node_cls is None:
            raise HaywireException(
                message=(
                    f"Node lookup failed for '{registry_key}' and no error node is "
                    f"registered. The application must register an error node with the "
                    f"node registry to provide a fallback."
                ),
                operation="Node Lookup",
                registry_key=registry_key,
                category="NodeFactoryConfigurationError",
            )
        return node_cls, node_error

    def _listen_on_lifecycle_event(self, batch: list[LifeCycleEvent]) -> None:
        """
        listener for node lifecycle changes from registry

        This is called by the NodeRegistry when a node class is reloaded, added,
        or removed. It forwards the notification to all registered hot reload
        listeners (typically NodeWrappers).

        Args:
            batch: The batch of events with complete context
        """
        # Forward to all lifecycle batch listeners (Context Menu, etc.)
        for listener in self._lifecycle_batch_subscribers[:]:
            listener(batch)

        # Forward to all individual event listeners
        for event in batch:
            library_label = event.library_identity.label if event.library_identity else "<unknown>"
            logger.info(
                f"NodeFactory: Node {event.event_type.value} - {event.registry_key} "
                f"from library '{library_label}'"
            )
            if event.registry_key in self._lifecycle_event_subscribers:
                callbacks = self._lifecycle_event_subscribers[event.registry_key]
                for callback in callbacks:
                    callback(event)

    ############################################################
    #
    #        Public API for lifecycle event listeners
    #
    ############################################################

    def add_batch_listener(self, callback: LifeCycleBatchCallback) -> None:
        """
        Add a callback for batch notifications.

        Args:
            callback: Function called with Batches of LifeCycleEvents
        """
        self._lifecycle_batch_subscribers.append(callback)

    def remove_batch_listener(self, callback: LifeCycleBatchCallback) -> None:
        """
        Remove a batch notification callback.

        Args:
            callback: The callback to remove
        """
        if callback in self._lifecycle_batch_subscribers:
            self._lifecycle_batch_subscribers.remove(callback)

    def add_event_subscriber(self, registry_key: str, callback: LifeCycleEventCallback) -> None:
        """
        Add a callback for event of specific registry_key.

        Args:
            registry_key: The registry key to listen for
            callback: Function called with LiveCycleEvent
        """
        if registry_key not in self._lifecycle_event_subscribers:
            self._lifecycle_event_subscribers[registry_key] = []
        self._lifecycle_event_subscribers[registry_key].append(callback)

    def remove_event_subscriber(self, registry_key: str, callback: LifeCycleEventCallback) -> None:
        """
        Remove a callback for event of specific registry_key.

        Args:
            registry_key: The registry key to stop listening for
            callback: The callback to remove
        """
        if registry_key in self._lifecycle_event_subscribers:
            if callback in self._lifecycle_event_subscribers[registry_key]:
                self._lifecycle_event_subscribers[registry_key].remove(callback)
                if not self._lifecycle_event_subscribers[registry_key]:
                    del self._lifecycle_event_subscribers[registry_key]

    # ============================================================================
    # Node Discovery and UI Services
    # ============================================================================

    def _build_node_info(self, registry_key: str) -> Optional[NodeInfo]:
        """Build composed node metadata from class identity and library information."""
        node_class = self.node_registry.get(registry_key)
        if node_class is None:
            return None

        identity = node_class.class_identity
        library_identity = getattr(node_class, "class_library", None)

        return NodeInfo(
            identity=identity,
            library=library_identity,
        )

    def get_menu_structure(self) -> Dict[str, List[NodeInfo]]:
        """
        Get nodes organized by menu path for UI building.

        Returns:
            Dictionary mapping menu paths to lists of node info dicts
        """
        menu: Dict[str, List[NodeInfo]] = {}

        for key in self.node_registry.list_names():
            node_info = self._build_node_info(key)
            if node_info is None:
                continue

            menu_path = node_info.identity.menu

            if menu_path not in menu:
                menu[menu_path] = []

            menu[menu_path].append(node_info)

        return menu

    def search_nodes(self, query: str) -> List[NodeInfo]:
        """
        Search for nodes matching a query string.

        Args:
            query: Search query string

        Returns:
            List of matching node info dicts
        """
        results: List[NodeInfo] = []
        query_lower = query.lower()

        for key in self.node_registry.list_names():
            node_info = self._build_node_info(key)
            if node_info is None:
                continue

            # Search in label, description, and tags
            searchable = [
                node_info.identity.label.lower(),
                node_info.identity.description.lower(),
                *[tag.lower() for tag in node_info.identity.search_tags],
            ]

            if any(query_lower in text for text in searchable):
                results.append(node_info)

        return results

    def list_all_nodes(self) -> List[str]:
        """
        Get list of all registered node registry keys.

        Returns:
            List of all registry keys
        """
        return self.node_registry.list_names()

    def get_node_info(self, registry_key: str) -> Optional[NodeInfo]:
        """
        Get detailed information about a specific node.

        Args:
            registry_key: Registry key of the node

        Returns:
            Dictionary with node information or None if not found
        """

        return self._build_node_info(registry_key)
