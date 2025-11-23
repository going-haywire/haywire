





import logging
from typing import Callable, List
from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.node.dataclasses import NodeErrorInfo
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LiveCycleBatchCallback
from haywire.core.types.ports import DataPort, PortInlet
from haywire.core.ui.widget.base import BaseWidget
from haywire.core.ui.widget.registry import WidgetRegistry
from haywire.ui.errors.error_info import render_error_info

NodeIDsBatchCallback = Callable[[set[str]], None]

class WidgetFactory:
    def __init__(self, widget_registry: WidgetRegistry):
        self._creators = {}
        self.widget_registry: WidgetRegistry = widget_registry

        # Customer callbacks for hot reload notifications
        self._widget_lifecycle_subscribers: List[LiveCycleBatchCallback] = []

        self.widget_registry.add_batch_event_subscriber(self._on_widget_reloaded)

        # Customer callbacks for hot reload notifications
        self._widget_lifecycle_subscribers: List[NodeIDsBatchCallback] = []

        self._widget_regkey_to_nodeids: dict[str, List[str]] = {}

    def add_widget_lifecycle_subscriber(self, callback: NodeIDsBatchCallback) -> None:
        """
        Add a customer callback for widget hot reload notifications.

        Args:
            callback: Function to call with affected node IDs when a widget is reloaded
        """
        self._widget_lifecycle_subscribers.append(callback)
    
    def remove_widget_lifecycle_subscriber(self, callback: NodeIDsBatchCallback) -> None:
        """
        Remove a previously added customer callback for widget hot reload notifications.

        Args:
            callback: Function to remove from the notification list
        """
        if callback in self._widget_lifecycle_subscribers:
            self._widget_lifecycle_subscribers.remove(callback)

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
            
            error_widget_registry_key = 'unknown'

            try:
                # get the error widget class from the registry
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
    
        self._widget_regkey_to_nodeids.setdefault(inlet.widget, []).append(node_id)
    
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
        node_ids_affected = set()

        # Forward to all individual event listeners
        for event in batch:
            for node_id in self._widget_regkey_to_nodeids.get(event.registry_key, []):
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
                self._widget_regkey_to_nodeids[widget_key].remove(node_id)