from typing import Any, Callable

import nicegui.ui as ui

from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleBatchCallback
from haywire.core.types import DataPort
from haywire.ui.widget.interface import IWidget
from haywire.ui.widget.registry import WidgetRegistry
from haywire.ui.errors.error_info import error_render_detail
from haywire.ui.widget.factory_interface import IWidgetFactory

NodeIDsBatchCallback = Callable[[set[str]], None]


class WidgetFactory(IWidgetFactory):
    """
    Factory class for creating widget instances using the WidgetRegistry.

    """

    def __init__(self, widget_registry: WidgetRegistry):
        self._creators: dict[str, Any] = {}
        self.widget_registry: WidgetRegistry = widget_registry

        # Customer callbacks for hot reload notifications
        self._widget_lifecycle_subscribers: set[LifeCycleBatchCallback] = set()

        self.widget_registry.add_batch_event_subscriber(self._on_widget_reloaded)

        self._widget_regkey_to_nodeids: dict[str, set[str]] = {}

    def add_widget_lifecycle_subscriber(self, callback: NodeIDsBatchCallback) -> None:
        """
        Add a customer callback for widget hot reload notifications.

        Args:
            callback: Function to call with affected node IDs when a widget is reloaded
        """
        self._widget_lifecycle_subscribers.add(callback)

    def remove_widget_lifecycle_subscriber(self, callback: NodeIDsBatchCallback) -> None:
        """
        Remove a previously added customer callback for widget hot reload notifications.

        Args:
            callback: Function to remove from the notification list
        """
        if callback in self._widget_lifecycle_subscribers:
            self._widget_lifecycle_subscribers.discard(callback)

    def render_widget(
        self, registry_key: str, port: DataPort, node_id: str
    ) -> tuple[IWidget | None, ui.element]:
        """Render a widget for the given inlet and return the widget instance.

        Note: The UI element is automatically added to the current NiceGUI context.

        Args:
            registry_key: The registry key of the widget to render
            port: The data port to render a widget for
            node_id: ID of the node containing this port

        Returns:
            IWidget instance or None if widget creation failed
        """
        widget_instance: IWidget | None = None

        ui_element: ui.element | None = None

        lc_event: LifeCycleEvent | None = None

        try:
            widget_instance, lc_event = self._get_widget(registry_key, port)
            ui_element = widget_instance.render()

        except Exception as error:
            library_identity = lc_event.library_identity if lc_event is not None else None
            module_name = lc_event.module_name if lc_event is not None else None
            # logging.error(f"Failed to render widget '{inlet.widget}' for inlet '{inlet.id}' "
            # f" in node '{node_id}': {error}", exc_info=True)
            if not isinstance(error, HaywireException):
                error = (
                    HaywireException.from_exception(
                        exception=error,
                        category="Widget Render Error",
                        operation="widget_lookup",
                        message=(
                            f"Failed to render widget '{port.widget_key}' "
                            f"for inlet '{port.id}' in node '{node_id}'"
                        ),
                    )
                    .enrich(
                        registry_key=port.widget_key,
                        library_identity=library_identity,
                        module_name=module_name,
                        suggestions=[
                            "Check if the widget class is implemented correctly",
                            "Ensure the widget library is properly loaded",
                        ],
                    )
                    .log()
                )

            ui_element = error_render_detail(error)

            return None, ui_element

        self._widget_regkey_to_nodeids.setdefault(port.widget_key, set()).add(node_id)

        return widget_instance, ui_element

    def _get_widget(self, registry_key: str, port: DataPort) -> tuple[IWidget | None, LifeCycleEvent | None]:
        """
        Get a widget instance for the given element using the widget registry.
        Args:
            registry_key: The registry key of the widget to render
            port: The DataPort (inlet or outlet) to get the widget for
        Returns:
            BaseWidget: The instantiated widget for the element or None
        """

        lc_event = self.widget_registry.get_widget_event(registry_key)

        widget_cls: type[IWidget] | None = lc_event.affected_class

        widget_instance = None

        if widget_cls is not None:
            try:
                widget_instance = widget_cls(port)

            except Exception as e:
                # Create detailed error with context about the node instantiation
                error = HaywireException.from_exception(
                    exception=e,
                    category="Widget Instantiation Error",
                    operation="widget_lookup",
                    message=f"Failed to instantiate widget '{registry_key}'",
                ).enrich(
                    registry_key=registry_key,
                    module_name=lc_event.module_name,
                    library_identity=lc_event.library_identity,
                )

                raise error
        return widget_instance, lc_event

    def _on_widget_reloaded(self, batch: list[LifeCycleEvent]) -> None:
        """
        Customer callback for widget hot reload events.

        This is called by the WidgetRegistry when a widget class is reloaded, added, or removed.
        Since widgets can be used by any renderer, we clear the entire cache.

        Args:
            event: The hot reload event with complete context
        """
        node_ids_affected = set()

        # Forward to all individual event listeners
        for event in batch:
            for node_id in self._widget_regkey_to_nodeids.get(event.registry_key, set()):
                node_ids_affected.add(node_id)

        for callback in self._widget_lifecycle_subscribers:
            callback(node_ids_affected)

    def cleanup(self):
        """Cleanup resources and unregister from registries."""
        self.widget_registry.remove_batch_event_subscriber(self._on_widget_reloaded)
        self._widget_lifecycle_subscribers.clear()
        self._widget_regkey_to_nodeids.clear()

    def unregister_widget_for_node(self, node_id: str):
        """Remove node ID from widget tracking when widget is destroyed."""
        for widget_key in self._widget_regkey_to_nodeids.keys():
            if node_id in self._widget_regkey_to_nodeids[widget_key]:
                self._widget_regkey_to_nodeids[widget_key].discard(node_id)
