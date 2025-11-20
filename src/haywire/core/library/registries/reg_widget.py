import inspect
import logging
from typing import TypeVar, Optional, Union, Type
import logging

from haywire.core.errors.utils import generate_haywire_error
from haywire.core.library.hot_reload_event import LifeCycleEvent, LifeCycleEventType

from ...data.fields import DataField
from ...ui.base_widget import BaseWidget
from ..library_identity import LibraryIdentity

from ..class_registry import BaseClassRegistry


class WidgetRegistry(BaseClassRegistry):
    """Registry for UI widgets that can render data fields"""

    def __init__(self):
        super().__init__()
        self._default_widgets: dict[Type, type] = {}
        self._error_widget: type | None = None

    def _class_filter(self, cls):
        try:
            return (inspect.isclass(cls) and
                    issubclass(cls, BaseWidget) and
                    cls != BaseWidget and
                    hasattr(cls, 'class_identity'))
        except TypeError:
            return False

    def _register_class(self, widget_cls: type[BaseWidget], library_identity: LibraryIdentity) -> str | None:
        """Register a UI widget with its metadata
        
        Uses the registry_key that was set by the @widget decorator during class definition.
        
        Args:
            widget: The widget class to register
            library_identity: Library metadata to use for setting widget attributes
        Returns:
            str: The haywire registry_key of the registered widget.
        """
        # Use registry_key that was set by the decorator
        registry_key = widget_cls.class_identity.registry_key

        # Check if this is an error node and register it automatically
        if widget_cls.class_identity._is_error:
            if self._error_widget is not None:
                if widget_cls.class_identity._error_priority > self._error_widget.class_identity._error_priority:
                    logging.warning(
                        f"Overriding already registered error node: '{self._error_widget.class_identity.registry_key}'."
                        f" with : '{widget_cls.class_identity.registry_key}'"
                        f" due to higher _error_priority ({widget_cls.class_identity._error_priority} > {self._error_widget.class_identity._error_priority})"
                    )
                    self._error_widget = widget_cls
            else:
                self._error_widget = widget_cls

        return super()._register(registry_key, widget_cls, library_identity)


    def _unregister_class(self, registry_key: str) -> type[BaseWidget] | None:
        """Unregister a UI widget by its registry key
        Args:
            registry_key: The haywire registry_key of the widget to unregister
        Returns:
            type[BaseWidget] | None: The unregistered widget class or None if not found
        """
        if self.get(registry_key) == self._error_widget:
            self._error_widget = None
            logging.warning(f"Error widget '{registry_key}' unregistered, no error widget left in registry")

        return super()._unregister(registry_key)

    def _get_error_widget(self) -> type[BaseWidget] | None:
        """Get the error widget class"""
        return self._error_widget
        
    def get_widget_event(self, key: str | None) -> type[LifeCycleEvent]:
        """
        Get last lifecycle widget event by registry key 

        Args:
            key: Registry key in format "library_id:widget:widget_name"

        Returns:
            LifeCycleEvent: Last lifecycle event for the widget
        """
        lifecycle_event = None

        if key in self._regkey_to_last_lifecycle_event:
            lifecycle_event = self._regkey_to_last_lifecycle_event[key]

        if lifecycle_event is None or lifecycle_event.is_successful_event() is False:
            error = generate_haywire_error(
                operation="Widget lookup",
                registry_key=key,
                message=f"Widget with registry key '{key}' not found"
            )
            lifecycle_event = LifeCycleEvent(
                registry_key=key,
                event_type=LifeCycleEventType.CLASS_NOT_FOUND,
                affected_class=self._get_error_widget(),
                error=error,
            )
 
        return lifecycle_event