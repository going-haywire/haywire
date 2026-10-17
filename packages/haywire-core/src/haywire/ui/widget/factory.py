from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

import nicegui.ui as ui

from haywire.core.access import LevelMode
from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.registry.lifecycle_event import LifeCycleEvent
from haywire.core.types import DataPort, WidgetModel
from haywire.ui.widget.interface import IWidget
from haywire.ui.widget.registry import WidgetRegistry
from haywire.ui.errors.error_info import error_render_detail
from haywire.ui.widget.factory_interface import IWidgetFactory

if TYPE_CHECKING:
    from haywire.core.graph.edit_route import EditRoute
    from haywire.core.settings.settings import Settings
    from haywire.ui.panel.setting_widget_model import SettingWidgetModel

NodeIDsBatchCallback = Callable[[set[str]], None]


def _widget_model_for(
    port: DataPort | WidgetModel, route: EditRoute | None = None, minimum: LevelMode = LevelMode.EDIT
) -> WidgetModel:
    """Return the model a widget for *port* binds to.

    A model that is not a ``DataPort`` is returned as given. A ``DataPort`` gets a
    ``SettingWidgetModel`` that reads the port's cell and sends each write to
    *route*, at level mode *minimum*: a promoted port's write goes to its setting
    (``EditRoute.set_setting``), any other to the port (``EditRoute.set_port``).
    With no route, or for a port of no node, the widget is read-only: each write
    is refused. A promoted port whose setting no longer resolves is written as a
    plain port.
    """
    if not isinstance(port, DataPort):
        return port

    from haywire.ui.panel.setting_widget_model import SettingWidgetModel

    return SettingWidgetModel(
        field_id=port.id,
        widget_config=port.widget_config,
        cell=port.data,
        on_edit=_write_for(port, route, minimum),
    )


def _write_for(port: DataPort, route: EditRoute | None, minimum: LevelMode) -> Callable[[Any], bool | None]:
    """Return where a widget write for *port* goes: its setting or the port, through *route*, or refused."""
    node = port._node
    if route is None or node is None:
        return _refuse
    resolved = None
    if port.promoted:
        from haywire.core.node.promotion import _resolve_promoted

        try:
            resolved = _resolve_promoted(node, port.id)
        except KeyError:
            pass
    if resolved is not None:
        bag, descriptor = resolved
        attr_name = descriptor._attr_name
        return lambda value: route.set_setting(bag, attr_name, value, minimum=minimum)
    return lambda value: route.set_port(node.node_id, port.id, value, minimum=minimum)


def setting_widget_model(
    bag: Settings, name: str, route: EditRoute | None, minimum: LevelMode
) -> SettingWidgetModel:
    """Return the model a widget for field *name* of *bag* binds to.

    The model reads the field's cell and sends each write to *route*, at level mode
    *minimum*; with no route every write is refused.

    Raises:
        KeyError: If *bag* has no field *name*.
    """
    from haywire.ui.panel.setting_widget_model import SettingWidgetModel

    descriptor = type(bag)._settings_descriptors()[name]

    def write(value: Any) -> bool:
        return route is not None and route.set_setting(bag, name, value, minimum=minimum)

    return SettingWidgetModel(
        field_id=name,
        widget_config=descriptor.widget_config,
        cell=bag._cell_for(descriptor),
        on_edit=write,
    )


def _refuse(_value: Any) -> bool:
    return False


class WidgetFactory(IWidgetFactory):
    """
    Factory class for creating widget instances using the WidgetRegistry.

    """

    def __init__(self, widget_registry: WidgetRegistry):
        self._creators: dict[str, Any] = {}
        self.widget_registry: WidgetRegistry = widget_registry

        # Customer callbacks for hot reload notifications
        self._widget_lifecycle_subscribers: set[NodeIDsBatchCallback] = set()

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
        self,
        registry_key: str,
        port: DataPort | WidgetModel,
        node_id: str,
        *,
        route: EditRoute | None = None,
        minimum: LevelMode = LevelMode.EDIT,
    ) -> tuple[IWidget | None, ui.element]:
        """Render a widget for the given inlet and return the widget instance.

        Note: The UI element is automatically added to the current NiceGUI context.

        Args:
            registry_key: The registry key of the widget to render
            port: The data port to render a widget for, or a model the caller built,
                which the widget binds to as given.
            node_id: ID of the node containing this port
            route: Where the widget's writes to a data port go; ``None`` refuses
                every write to a data port.
            minimum: The lowest level mode at which *route* lets a write through.

        Returns:
            IWidget instance or None if widget creation failed
        """
        widget_instance: IWidget | None = None
        widget_key = port.widget_key if isinstance(port, DataPort) else registry_key

        ui_element: ui.element | None = None

        lc_event: LifeCycleEvent | None = None

        try:
            widget_instance, lc_event = self._get_widget(
                registry_key, _widget_model_for(port, route, minimum)
            )
            if widget_instance is None:
                raise HaywireException.create(message=f"Widget '{registry_key}' not found")
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
                            f"Failed to render widget '{widget_key}' "
                            f"for inlet '{port.id}' in node '{node_id}'"
                        ),
                    )
                    .enrich(
                        registry_key=widget_key,
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

        if widget_key is not None:
            self._widget_regkey_to_nodeids.setdefault(widget_key, set()).add(node_id)

        return widget_instance, ui_element

    def _get_widget(
        self, registry_key: str, model: WidgetModel
    ) -> tuple[IWidget | None, LifeCycleEvent | None]:
        """
        Get a widget instance for the given element using the widget registry.
        Args:
            registry_key: The registry key of the widget to render
            model: The model the widget binds to
        Returns:
            BaseWidget: The instantiated widget for the element or None
        """

        lc_event = self.widget_registry.get_widget_event(registry_key)

        widget_cls: type[IWidget] | None = lc_event.affected_class

        widget_instance = None

        if widget_cls is not None:
            try:
                widget_instance = widget_cls(model)

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

                raise error from e
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
