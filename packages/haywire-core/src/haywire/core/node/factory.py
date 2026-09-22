"""Resolve node classes by registry key, and fan lifecycle events out to their subscribers."""

import logging
from typing import TYPE_CHECKING, Dict, List, Optional

from haywire.core.errors.haywire_exception import HaywireException
from . import BaseNode, NodeRegistry
from .info import NodeInfo

from ..registry.lifecycle_event import LifeCycleEvent, LifeCycleBatchCallback, LifeCycleEventCallback

if TYPE_CHECKING:
    from ..macro.registry import MacroRegistry

logger = logging.getLogger(__name__)


def _kind_of(registry_key: str) -> str:
    """The kind segment of a registry key (``lib:node:Name`` -> ``node``)."""
    parts = registry_key.split(":")
    return parts[1] if len(parts) > 2 else ""


class NodeFactory:
    """Resolves node classes by registry key and relays the registry's lifecycle events.

    Subscribe with ``add_batch_listener`` for every event, or with
    ``add_event_subscriber`` for one registry key. Graph lifecycle and undo are
    not its concern.

    Discovery — the menu, search and the key listing — spans the node registry
    and the macro registry, so a macro is offered like any other component.
    """

    def __init__(self, node_registry: NodeRegistry, macro_registry: "MacroRegistry | None" = None):
        """Initialize the factory and subscribe it to its registries' lifecycle events.

        Args:
            macro_registry: Supplies macros to the discovery APIs. Omit it for
                a headless factory that resolves node classes only.
        """
        self.node_registry = node_registry
        self.macro_registry = macro_registry

        # batch notification callbacks
        self._lifecycle_batch_subscribers: List[LifeCycleBatchCallback] = []

        # individual event notification callbacks
        # registry_key -> list of callbacks
        self._lifecycle_event_subscribers: Dict[str, List[LifeCycleEventCallback]] = {}

        self.node_registry.add_batch_event_subscriber(self._listen_on_lifecycle_event)
        if self.macro_registry is not None:
            # Same relay: a placement subscribes per registry key, so a macro
            # reload reaches every card standing for it.
            self.macro_registry.add_batch_event_subscriber(self._listen_on_lifecycle_event)

    def get_alternate_node_registry_keys(self, registry_key: str) -> list[str]:
        """The registry keys of same-named nodes from other libraries. See
        ``NodeRegistry.get_alternate_node_registry_keys``."""
        alternates = self.node_registry.get_alternate_node_registry_keys(registry_key)
        return alternates

    def get_node(self, registry_key: str) -> tuple[type[BaseNode], HaywireException | None]:
        """Return the class to instantiate for ``registry_key``, and any error explaining
        why it is not the requested one.

        Falls back to the registered error node when the key is unknown or its
        last registry event failed.

        Raises:
            HaywireException: If the key yields no class and no error node is
                registered at all.
        """
        if _kind_of(registry_key) == "macro":
            return self._get_macro_node(registry_key)

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

    def _get_macro_node(self, registry_key: str) -> tuple[type[BaseNode], HaywireException | None]:
        """Return the placement card for a macro key, and any error about the macro.

        The card class is the same for every macro — a placement is told which
        template it stands for by its own ``registry_key``, not by its class.
        A key with no registered template takes the error-node path, so a graph
        using a macro from an absent library still opens.
        """
        error: HaywireException | None = None
        template = self.macro_registry.template(registry_key) if self.macro_registry else None
        if template is None:
            error = HaywireException(
                message=f"Macro with registry key '{registry_key}' not found in registry.",
                operation="Macro Lookup",
                registry_key=registry_key,
                category="NodeNotFoundError",
                suggestions=[
                    "Ensure the library providing this macro is installed and enabled.",
                    "Check that the macro's .hwm file is still in the library's macros folder.",
                ],
            )

        macro_cls = self.node_registry._get_macro_node() if template is not None else None
        if macro_cls is None:
            macro_cls = self.node_registry._get_error_node()
        if macro_cls is None:
            raise HaywireException(
                message=(
                    f"Macro lookup failed for '{registry_key}' and no error node is "
                    f"registered. The application must register an error node with the "
                    f"node registry to provide a fallback."
                ),
                operation="Macro Lookup",
                registry_key=registry_key,
                category="NodeFactoryConfigurationError",
            )
        return macro_cls, error

    def _listen_on_lifecycle_event(self, batch: list[LifeCycleEvent]) -> None:
        """Relay a batch of registry lifecycle events to the batch listeners, then each
        event to the subscribers of its registry key."""
        for listener in self._lifecycle_batch_subscribers[:]:
            listener(batch)

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
        """Call *callback* with every batch of lifecycle events."""
        self._lifecycle_batch_subscribers.append(callback)

    def remove_batch_listener(self, callback: LifeCycleBatchCallback) -> None:
        """Stop calling *callback* with lifecycle batches. Unknown callbacks are ignored."""
        if callback in self._lifecycle_batch_subscribers:
            self._lifecycle_batch_subscribers.remove(callback)

    def add_event_subscriber(self, registry_key: str, callback: LifeCycleEventCallback) -> None:
        """Call *callback* with each lifecycle event for ``registry_key``."""
        if registry_key not in self._lifecycle_event_subscribers:
            self._lifecycle_event_subscribers[registry_key] = []
        self._lifecycle_event_subscribers[registry_key].append(callback)

    def remove_event_subscriber(self, registry_key: str, callback: LifeCycleEventCallback) -> None:
        """Stop calling *callback* for ``registry_key``. Unknown pairs are ignored."""
        if registry_key in self._lifecycle_event_subscribers:
            if callback in self._lifecycle_event_subscribers[registry_key]:
                self._lifecycle_event_subscribers[registry_key].remove(callback)
                if not self._lifecycle_event_subscribers[registry_key]:
                    del self._lifecycle_event_subscribers[registry_key]

    # ============================================================================
    # Node Discovery and UI Services
    # ============================================================================

    def _build_node_info(self, registry_key: str) -> Optional[NodeInfo]:
        """The component's composed metadata, or ``None`` if the key is not registered.

        Resolves a macro key off the macro registry, whose templates carry the
        same ``class_identity``/``class_library`` pair a node class does.
        """
        node_class = self.node_registry.get(registry_key)
        if node_class is not None:
            return NodeInfo(
                identity=node_class.class_identity,
                library=getattr(node_class, "class_library", None),
            )

        if self.macro_registry is not None:
            template = self.macro_registry.template(registry_key)
            if template is not None:
                return NodeInfo(
                    identity=template.class_identity,
                    library=template.class_library,
                    is_macro=True,
                )

        return None

    def _visible_keys(self) -> List[str]:
        """Every key the create menu and search may offer, nodes then macros."""
        keys = list(self.node_registry.list_visible_names())
        if self.macro_registry is not None:
            keys.extend(self.macro_registry.list_visible_names())
        return keys

    def get_reroute_node(self) -> type[BaseNode] | None:
        """Return the reroute provider class (node registered with _is_reroute),
        or None if no loaded library provides one."""
        return self.node_registry._get_reroute_node()

    def get_subgraph_input_node(self) -> type[BaseNode] | None:
        """Return the Subgraph Input boundary class (node registered with
        _is_subgraph_input), or None if no loaded library provides one."""
        return self.node_registry._get_subgraph_input_node()

    def get_subgraph_output_node(self) -> type[BaseNode] | None:
        """Return the Subgraph Output boundary class (node registered with
        _is_subgraph_output), or None if no loaded library provides one."""
        return self.node_registry._get_subgraph_output_node()

    def get_graph_node(self) -> type[BaseNode] | None:
        """Return the Graph-node class (node registered with _is_graph_node),
        or None if no loaded library provides one."""
        return self.node_registry._get_graph_node()

    def get_menu_structure(self) -> Dict[str, List[NodeInfo]]:
        """Return every visible node's ``NodeInfo``, grouped by its menu path.

        A node with no menu path lands under ``"misc"``. Hidden nodes are left
        out, so they stay usable but are never offered in the create menu.
        """
        menu: Dict[str, List[NodeInfo]] = {}

        for key in self._visible_keys():
            node_info = self._build_node_info(key)
            if node_info is None:
                continue

            menu_path = node_info.identity.menu or "misc"

            if menu_path not in menu:
                menu[menu_path] = []

            menu[menu_path].append(node_info)

        return menu

    def search_nodes(self, query: str) -> List[NodeInfo]:
        """Return the visible nodes whose label, description or search tags contain
        *query*, matched case-insensitively."""
        results: List[NodeInfo] = []
        query_lower = query.lower()

        for key in self._visible_keys():
            node_info = self._build_node_info(key)
            if node_info is None:
                continue

            searchable = [
                node_info.identity.label.lower(),
                node_info.identity.description.lower(),
                *[tag.lower() for tag in node_info.identity.search_tags],
            ]

            if any(query_lower in text for text in searchable):
                results.append(node_info)

        return results

    def list_all_nodes(self) -> List[str]:
        """Every registered node and macro registry key, hidden ones included."""
        keys = list(self.node_registry.list_names())
        if self.macro_registry is not None:
            keys.extend(self.macro_registry.list_names())
        return keys

    def get_node_info(self, registry_key: str) -> Optional[NodeInfo]:
        """The node's ``NodeInfo``, or ``None`` if the key is not registered."""

        return self._build_node_info(registry_key)
