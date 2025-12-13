import inspect
import logging
from typing import Optional

from haywire.core.errors.haywire_exception import ErrorSeverity, HaywireException
from haywire.core.registry.lifecycle_event import LifeCycleEvent
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import BaseRegistry

from .interface import IBaseRenderer

class RendererRegistry(BaseRegistry):
    """Registry for NodeRenderer classes with fallback support"""

    def __init__(self):
        super().__init__()
        self._default_renderer_name: str | None = None
        self._default_priority: int = -1
        self._error_renderer_name: str | None = None
        self._error_priority: int = -1

        self._error_renderer: type[IBaseRenderer] | None = None

    def _class_filter(self, cls):
        try:
            return (inspect.isclass(cls) and
                    issubclass(cls, IBaseRenderer) and
                    cls != IBaseRenderer and
                    hasattr(cls, 'class_identity'))
        except TypeError:
            return False

    def _register_class(
        self,
        renderer_cls: type[IBaseRenderer],
        library_identity: Optional[LibraryIdentity] = None
    ) -> str | None:
        """
        Register a renderer class.
        
        Uses the registry_key that was set by the @renderer decorator during class definition.
        
        Args:
            renderer_class: The NodeRenderer class
            library_identity: Optional library metadata for the renderer.
        Returns:
            str: The haywire registry_key of the registered renderer.
        """
        # Use registry_key that was set by the decorator
        registry_key = renderer_cls.class_identity.registry_key


        # Check if this is an error node and register it automatically
        if renderer_cls.class_identity._is_error:
            if self._error_renderer is not None:
                if (
                    renderer_cls.class_identity._error_priority > 
                    self._error_renderer.class_identity._error_priority
                ):
                    logging.warning(
                        f"Overriding already registered error renderer: "
                        f"'{self._error_renderer.class_identity.registry_key}'"
                        f" with : '{renderer_cls.class_identity.registry_key}'"
                        f" due to higher _error_priority "
                        f"({renderer_cls.class_identity._error_priority} > "
                        f"{self._error_renderer.class_identity._error_priority})"
                    )
                    self._error_renderer = renderer_cls
            else:
                self._error_renderer = renderer_cls

        # Check if this is an error node and register it as such
        if renderer_cls.class_identity._is_error:
            new_error_priority = renderer_cls.class_identity._error_priority
            if new_error_priority > self._error_priority:
                if self._error_renderer_name:
                    logging.warning(
                        f"Overriding already registered error renderer: "
                        f"'{self._error_renderer_name}'"
                        f" with : '{registry_key}'"
                        f" due to higher _error_priority "
                        f"({new_error_priority} > {self._error_priority})"
                    )
                self._error_renderer_name = registry_key
                self._error_priority = new_error_priority


        # Check if this is an default node and register it as such
        if renderer_cls.class_identity._is_default:
            new_default_priority = renderer_cls.class_identity._default_priority
            if new_default_priority > self._default_priority:
                if self._default_renderer_name:
                    logging.warning(
                        f"Overriding already registered default renderer: "
                        f"'{self._default_renderer_name}'"
                        f" with : '{registry_key}'"
                        f" due to higher _default_priority "
                        f"({new_default_priority} > {self._default_priority})"
                    )
                self._default_renderer_name = registry_key
                self._default_priority = new_default_priority

        return super()._register(registry_key, renderer_cls, library_identity)

    def _unregister_class(self, registry_key: str) -> type[IBaseRenderer] | None:
        """Unregister a renderer by its registry_key
        Args:
            registry_key: The haywire registry_key of the renderer to unregister
        Returns:
            type[BaseNodeRenderer] | None: The unregistered renderer class or None if not found
        """
        removed_class = super()._unregister(registry_key)
        
        if removed_class == self._error_renderer:
            self._error_renderer = None
            logging.warning(
                f"Error renderer '{registry_key}' unregistered, "
                "no error renderer left in registry"
            )    
        
        return removed_class
   
    def get_default_renderer_registry_key(self) -> str | None:
        """Get the default renderer registry key"""
        return self._default_renderer_name

    def get_error_renderer_registry_key(self) -> str | None:
        """Get the error renderer registry key"""
        return self._error_renderer_name
        
    def get_renderer_event(self, key: str | None) -> type[LifeCycleEvent]:
        """
        Get last lifecycle renderer event by registry key 

        Args:
            key: Registry key in format "library_id:renderer:renderer_name"

        Returns:
            LifeCycleEvent: Last lifecycle event for the renderer
            
        Raises:
            HaywireException: If renderer not found or last event unsuccessful
        """
        lifecycle_event = None

        if key in self._regkey_to_last_lifecycle_event:
            lifecycle_event = self._regkey_to_last_lifecycle_event[key]

        if lifecycle_event is None:
            error = HaywireException.create(
                message=f"Renderer '{key}' not found, using error renderer as fallback",
                severity=ErrorSeverity.ERROR,
                category="Renderer Not Found",
                operation="renderer_lookup",
                registry_key=key,
                suggestions=[
                    "Try using existing renderer instead",
                    "Library containing the renderer may have failed to load"
                ],
                auto_retry=True
            )
            raise error
        elif lifecycle_event.error:
            raise lifecycle_event.error
        elif not lifecycle_event.is_successful_event():
            error = HaywireException.create(
                message=f"Renderer '{key}' failed to load, due to '{lifecycle_event.event_type}' ",
                severity=ErrorSeverity.ERROR,
                category="Renderer Load Error",
                operation="renderer_lookup",
                registry_key=key,
                suggestions=[
                    "Renderer may have been removed",
                    "Library containing the renderer may been disabled"
                ],
                auto_retry=True
            )
            raise error
 

        return lifecycle_event