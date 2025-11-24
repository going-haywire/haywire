import inspect
import logging
from typing import Any, Dict, Optional, TypeVar, Union

from haywire.core.errors.haywire_exception import ErrorSeverity, HaywireException
from haywire.core.registry.lifecycle_event import LifeCycleEvent

from .interface import IBaseRenderer
from ...library.identity import LibraryIdentity
from ...registry.base import BaseRegistry

class RendererRegistry(BaseRegistry):
    """Registry for NodeRenderer classes with fallback support"""

    def __init__(self):
        super().__init__()
        self._default_renderer_name: str | None = None
        self._error_renderer_name: str | None = None
        self._error_renderer: type[IBaseRenderer] | None = None

    def _class_filter(self, cls):
        try:
            return (inspect.isclass(cls) and
                    issubclass(cls, IBaseRenderer) and
                    cls != IBaseRenderer and
                    hasattr(cls, 'class_identity'))
        except TypeError:
            return False

    def _register_class(self, renderer_cls: type[IBaseRenderer], library_identity: Optional[LibraryIdentity] = None) -> str | None:
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

        # Check if this is an error renderer and register it automatically
        if renderer_cls.class_identity.is_error:
            self._error_renderer_name = registry_key
            self._error_renderer = renderer_cls
        # Check if this is a default renderer and register it automatically
        elif renderer_cls.class_identity.is_default:
            self._default_renderer_name = registry_key
        elif self._default_renderer_name is None:
            # Automatically set as default if no default is set yet
            self._default_renderer_name = registry_key

        return super()._register(registry_key, renderer_cls, library_identity)

    def _unregister_class(self, registry_key: str) -> type[IBaseRenderer] | None:
        """Unregister a renderer by its registry_key
        Args:
            registry_key: The haywire registry_key of the renderer to unregister
        Returns:
            type[BaseNodeRenderer] | None: The unregistered renderer class or None if not found
        """
        removed_class = super()._unregister(registry_key)

        if self._default_renderer_name == registry_key:
            self._default_renderer_name = None
            for key in self._classes.keys():
                if key != self._error_renderer_name:
                    self._default_renderer_name = key
        
        if self._default_renderer_name is None:
            logging.warning(f"Default renderer '{registry_key}' unregistered, no renderers left in registry")
        
        if removed_class == self._error_renderer:
            self._error_renderer = None
            logging.warning(f"Error renderer '{registry_key}' unregistered, no error renderer left in registry")    
        
        return removed_class

    def get_renderer_class(self, renderer_name: str | None) -> type[IBaseRenderer]:
        """
        Get renderer class with fallback strategy:
        1. Try exact renderer name lookup
        2. Use default if no renderer name is specified
        3. Return error renderer if exact renderer doesn't exist
        4. Escalate with RuntimeError exception if no error renderer registered
        """
        # 1. Try exact renderer name lookup
        if renderer_name and self.has(renderer_name):
            return self._classes[renderer_name]

        # 2. Use default if no renderer name is specified
        if renderer_name is None and self._default_renderer_name:
            if self.has(self._default_renderer_name):
                return self._classes[self._default_renderer_name]

        # 3. Return error renderer if exact renderer doesn't exist
        if self._error_renderer:
            return self._error_renderer
        
        # Fallback if no error renderer registered
        raise RuntimeError(f"No renderer found for '{renderer_name}' and no error renderer registered")

    def get_default_renderer(self) -> type[IBaseRenderer] | None:
        """Get the default renderer class"""
        if self._default_renderer_name:
            if self.has(self._default_renderer_name):
                return self._classes[self._default_renderer_name]
        return None
    
    def get_default_renderer_registry_key(self) -> str | None:
        """Get the default renderer registry key"""
        return self._default_renderer_name
    
    def get_error_renderer(self) -> type[IBaseRenderer] | None:
        """Get the error renderer class"""
        return self._error_renderer
    
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