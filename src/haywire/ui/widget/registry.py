import inspect

from haywire.core.errors.haywire_exception import HaywireException, ErrorSeverity
from haywire.core.registry.lifecycle_event import LifeCycleEvent
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import BaseRegistry

from .base import BaseWidget
from .globals import register_widget_globally, unregister_widget_globally

class WidgetRegistry(BaseRegistry):
    """Registry for UI widgets that can render data fields"""

    def __init__(self):
        super().__init__()

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
        
        reg = super()._register(registry_key, widget_cls, library_identity)

        if reg:
            register_widget_globally(registry_key, widget_cls)

        return reg


    def _unregister_class(self, registry_key: str) -> type[BaseWidget] | None:
        """Unregister a UI widget by its registry key
        Args:
            registry_key: The haywire registry_key of the widget to unregister
        Returns:
            type[BaseWidget] | None: The unregistered widget class or None if not found
        """
        unreg = super()._unregister(registry_key)
        
        unregister_widget_globally(registry_key)

        return unreg
        
    def get_widget_event(self, key: str | None) -> type[LifeCycleEvent]:
        """
        Get last lifecycle widget event by registry key 

        Args:
            key: Registry key in format "library_id:widget:widget_name"

        Returns:
            LifeCycleEvent: Last lifecycle event for the widget
            
        Raises:
            HaywireException: If widget not found or last event unsuccessful
        """
        lifecycle_event = None

        if key in self._regkey_to_last_lifecycle_event:
            lifecycle_event = self._regkey_to_last_lifecycle_event[key]

        if lifecycle_event is None or lifecycle_event.is_successful_event() is False:
            error = HaywireException.create(
                message=f"Widget '{key}' not found, using error widget",
                severity=ErrorSeverity.ERROR,
                category="Widget Not Found",
                operation="widget_lookup",
                registry_key=key,
                suggestions=[
                    "Using default error widget as fallback",
                    "Check if the widget library is properly loaded"
                ],
                auto_retry=True
            )
            raise error

        return lifecycle_event