"""
SkinFactory - Factory for creating UINodeCard instances using NodeSkin classes

This factory manages cached NodeSkin instances and provides the render method
that looks up skins from the skin registry.

Enhanced with customer notification system for UINode hot reload support.
"""

import logging
from typing import Callable, Dict

from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.registry.lifecycle_event import LifeCycleEvent
from haywire.core.node.node_wrapper import NodeWrapper

from ..widget.factory import WidgetFactory
from .base import BaseSkin
from .registry import SkinRegistry
from .nodecard import UINodeCard


FactoryEventCallback = Callable[[], None]  # Function signature for factory event callbacks

NO_SKIN_DEFINED: str = "no.skin.defined"


class SkinFactory:
    """
    Factory class for creating UINodeCard instances using NodeSkin classes.

    This factory:
    - Has access to both skin registry and widgets registry
    - Caches stateless NodeSkin instances for reuse
    - Provides render method for creating UINodeCard instances
    - Notifies customers (UINodes) when skins are hot-reloaded
    """

    def __init__(self, skin_registry: SkinRegistry, widget_factory: WidgetFactory):
        """
        Initialize the factory with registries.

        Args:
            skin_registry: Registry for NodeSkin classes
            widget_factory: Factory for creating widget instances
        """
        self._skin_registry: SkinRegistry = skin_registry

        self._widget_factory = widget_factory

        # Subscribe to widget factory lifecycle events
        self._widget_factory.add_widget_lifecycle_subscriber(self._listen_on_widget_lifecycle_events)

        # Subscribe to skin registry lifecycle events
        self._skin_registry.add_batch_event_subscriber(self._listen_on_skin_lifecycle_event)

        # Cache for BaseSkin instances by registry key
        self._skin_instance_cache: Dict[str, BaseSkin] = {}

        # Customer callbacks for factory hot reload notifications
        # mapping from node_id key to callback functions of each individual UINode
        self._nodeid_to_factory_subscriber: dict[str, set[FactoryEventCallback]] = {}

        # Mapping from skin registry key to the wrapper node id that uses that skin
        self._skin_regkey_to_node_id: dict[str, set[str]] = {}

        # Mapping from node id to the skin registry key it uses
        # this is used to help cleaning up the _skin_regkey_to_node_id mapping
        self._nodeid_to_skin_regkey: dict[str, str] = {}

        self.logger = logging.getLogger(__name__)

    # this method is called by UINode to render the node
    def render(
        self, skin_registry_key: str, wrapper: NodeWrapper, _is_error_render: bool = False
    ) -> UINodeCard | None:
        """Render a node with the skin identified by skin_registry_key.

        Callers are responsible for resolving the skin registry key
        (e.g. falling back to the registry's default skin) before invoking
        this method.

        Args:
            skin_registry_key: The registry key of the skin to use
            wrapper: NodeWrapper instance containing node information

        Returns:
            UINodeCard instance or None if rendering failed
        """
        ui_nodeCard: UINodeCard | None = None

        skin_instance: BaseSkin | None = None

        try:
            skin_instance = self.get_skin_instance(skin_registry_key)

            ui_nodeCard = skin_instance._render(wrapper=wrapper)

        except Exception as error:
            if not isinstance(error, HaywireException):
                error = HaywireException.from_exception(
                    exception=error,
                    message=(
                        f"Failed to use skin '{skin_registry_key}' "
                        f"for node '{wrapper.node.identity.label}' "
                        f"with node id '{wrapper.node_id}'"
                    ),
                    suggestions=[
                        "Ensure the node's specified skin is implemented",
                        "Inside the node definition check for spelling mistakes in the skin registry key",
                        "Check the log for errors - the skin might have failed to load",
                    ],
                    category="Render Error",
                    operation="skin_lookup",
                    library_identity=(skin_instance.__class__.class_library if skin_instance else None),
                    registry_key=skin_registry_key,
                )

            error.log(self.logger)

            if _is_error_render:
                # Prevent infinite recursion. If there is something wrong with the error skin,
                # we cannot recover from this.

                self.logger.debug(
                    f" -> Emergency Fallback to render error '{error.message}' "
                    f"on '{wrapper.node.identity.label}' - '{wrapper.node_id}' "
                    f"without skin"
                )
                if ui_nodeCard is None:
                    ui_nodeCard = UINodeCard()

                ui_nodeCard.append(error)

                return ui_nodeCard

            error_skin_registry_key = self._skin_registry.get_error_skin_registry_key()

            if error_skin_registry_key is None:
                # No error skin available — emergency fallback inline
                ui_nodeCard = UINodeCard()
                ui_nodeCard.append(error)
                return ui_nodeCard

            # render error (recursive call with error render flag)
            ui_nodeCard = self.render(
                skin_registry_key=error_skin_registry_key, wrapper=wrapper, _is_error_render=True
            )

            assert ui_nodeCard is not None, "_is_error_render path always returns a UINodeCard"
            ui_nodeCard.append(error)

        return ui_nodeCard

    def get_skin_instance(self, registry_key: str) -> BaseSkin:
        """
        Get a skin instance for the given element using the skin registry.
        Args:
            registry_key: The registry key to get the skin for
        Returns:
            BaseSkin: The instantiated skin for the registry key
        Raises:
            HaywireException: If the skin is not found or fails to instantiate
        """

        lc_event = self._skin_registry.get_skin_event(registry_key)

        skin_cls: type[BaseSkin] | None = lc_event.affected_class

        if skin_cls is None:
            raise HaywireException.create(
                category="Skin Lookup Error",
                operation="skin_lookup",
                message=f"Skin '{registry_key}' not found in registry",
            ).enrich(
                registry_key=registry_key,
                module_name=lc_event.module_name,
                library_identity=lc_event.library_identity,
            )

        try:
            if registry_key in self._skin_instance_cache:
                return self._skin_instance_cache[registry_key]
            skin_instance = skin_cls(self._widget_factory)
            self._skin_instance_cache[registry_key] = skin_instance
            return skin_instance

        except Exception as e:
            # Create detailed error with context about the node instantiation
            error = HaywireException.from_exception(
                exception=e,
                category="Skin Instantiation Error",
                operation="skin_lookup",
                message=f"Failed to instantiate skin '{registry_key}'",
            ).enrich(
                registry_key=registry_key,
                module_name=lc_event.module_name,
                library_identity=lc_event.library_identity,
            )

            raise error

    def add_factory_lifecycle_subscriber(
        self, node_id: str, skin_registry_key: str, callback: FactoryEventCallback
    ) -> None:
        """
        Register a customer callback for factory event notifications.

        Callbacks are invoked when either
        - a skin is hot-reloaded, added, or removed.
        - a widget is hot-reloaded, added, or removed.

        Args:
            node_id: The ID of the node to associate with the callback
            skin_registry_key: The registry key of the skin the node uses
            callback: Function with signature FactoryEventCallback
        """
        # Cleanup previous skin mappings if re-subscribing with different skin
        if node_id in self._nodeid_to_skin_regkey:
            previous_regkey = self._nodeid_to_skin_regkey[node_id]
            if node_id in self._skin_regkey_to_node_id.get(previous_regkey, set()):
                self._skin_regkey_to_node_id[previous_regkey].remove(node_id)
                self.logger.debug(
                    f"  -> Cleanup skin_key to node_id mapping: '{previous_regkey}' -> '{node_id}'"
                )

        # Setup skin to node_id mappings for hot reload tracking
        # one to many mapping
        self._skin_regkey_to_node_id.setdefault(skin_registry_key, set()).add(node_id)
        # one to one mapping
        self._nodeid_to_skin_regkey[node_id] = skin_registry_key
        self.logger.debug(f"  -> Setup skin_key to node_id mapping: '{skin_registry_key}' -> '{node_id}'")

        self._nodeid_to_factory_subscriber.setdefault(node_id, set()).add(callback)

    def remove_factory_lifecycle_subscriber(self, node_id: str, callback: FactoryEventCallback) -> None:
        """
        Unregister a customer callback and clean up skin mappings.

        Args:
            node_id: The ID of the node associated with the callback
            callback: The callback function to remove
        """
        if node_id in self._nodeid_to_factory_subscriber:
            if callback in self._nodeid_to_factory_subscriber[node_id]:
                self._nodeid_to_factory_subscriber[node_id].remove(callback)

            if len(self._nodeid_to_factory_subscriber[node_id]) == 0:
                del self._nodeid_to_factory_subscriber[node_id]
                # Also cleanup skin mappings when no more subscribers for this node
                if node_id in self._nodeid_to_skin_regkey:
                    reg_key = self._nodeid_to_skin_regkey[node_id]
                    if node_id in self._skin_regkey_to_node_id.get(reg_key, set()):
                        self._skin_regkey_to_node_id[reg_key].remove(node_id)
                    del self._nodeid_to_skin_regkey[node_id]

    def _notify_factory_subscribers(self, node_id: str) -> None:
        """
        Notify all subscribers about lifecycle events affected
        by changes of skin and widgets the factory has detected.

        Args:
            node_id: The ID of the node affected by the lifecycle event
        """
        if node_id in self._nodeid_to_factory_subscriber:
            for callback in self._nodeid_to_factory_subscriber[node_id]:
                self.logger.debug(f" Node {node_id} lifecycle event notification ")
                callback()

    def _listen_on_skin_lifecycle_event(self, batch: list[LifeCycleEvent]) -> None:
        """
        Listener for skin hot reload events is called by the SkinRegistry
        when a skin class is reloaded, added, or removed.
        It clears the cache for affected skins.

        Args:
            batch: List of lifecycle events with complete context
        """
        # Forward to all individual event listeners
        for event in batch:
            if event.registry_key:
                self.logger.info(
                    f"SkinFactory: Node {event.event_type.value} - {event.registry_key} "
                    f"from library '{event.library_identity.label}'"
                )
                # Clear cache for affected skin
                if event.registry_key in self._skin_instance_cache:
                    del self._skin_instance_cache[event.registry_key]
                else:
                    # in this case the skin has never been used/cached before.
                    # if nodes have been rendering with a non existing skin
                    # (most likely the error skin), they might be interested to
                    # know about that new skin and should be informed
                    node_ids = set(self._skin_regkey_to_node_id.get(NO_SKIN_DEFINED, set()))

                    for node_id in node_ids:
                        self._notify_factory_subscribers(node_id)

                # Notify customers (UINodes) about the skin reload
                reg_key = event.registry_key
                node_ids = set(self._skin_regkey_to_node_id.get(reg_key, set()))
                for node_id in node_ids:
                    self._notify_factory_subscribers(node_id)

    def _listen_on_widget_lifecycle_events(self, node_ids: set[str]):
        """
        Listener for widget lifecycle events emitted by the widget factory

        it directly forwards the affected node IDs to the factory subscribers.

        Args:
            node_ids: Set of node IDs affected by the widget lifecycle event
        """
        for node_id in node_ids:
            self._notify_factory_subscribers(node_id)

    def _unregister_node(self, node_id: str):
        """
        Remove node ID tracking from both skin and widget factories
        when node is destroyed.
        Args:
            node_id: The node ID to unregister
        """
        reg_key = self._nodeid_to_skin_regkey.get(node_id, None)
        self.logger.debug(f" -> Unregister node for rendering '{node_id}' with skin '{reg_key}'")
        if reg_key:
            if self._skin_regkey_to_node_id[reg_key]:
                if node_id in self._skin_regkey_to_node_id[reg_key]:
                    self._skin_regkey_to_node_id[reg_key].remove(node_id)
            del self._nodeid_to_skin_regkey[node_id]
        self._widget_factory.unregister_widget_for_node(node_id)

    def cleanup(self):
        """Cleanup resources and unregister from registries."""
        self._skin_registry.remove_batch_event_subscriber(self._listen_on_skin_lifecycle_event)

        self._widget_factory.remove_widget_lifecycle_subscriber(self._listen_on_widget_lifecycle_events)

        self._nodeid_to_factory_subscriber.clear()
        self.reset_cache()

    def reset_cache(self):
        """Clear all cached skin instances."""
        self._skin_instance_cache.clear()
