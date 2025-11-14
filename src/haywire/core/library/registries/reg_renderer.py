import inspect
import logging
from typing import Any, Dict, Optional, TypeVar, Union

from ..library_identity import LibraryIdentity
from ...ui.base_renderer import BaseNodeRenderer

from ..class_registry import BaseClassRegistry
from ..utils import reg_key

class RendererRegistry(BaseClassRegistry):
    """Registry for NodeRenderer classes with fallback support"""

    def __init__(self):
        super().__init__()
        self._default_renderer_name: str | None = None
        self._error_renderer: type | None = None

    def _class_filter(self, cls):
        try:
            return (inspect.isclass(cls) and
                    issubclass(cls, BaseNodeRenderer) and
                    cls != BaseNodeRenderer and
                    hasattr(cls, 'class_identity'))
        except TypeError:
            return False

    def _register_class(self, renderer_cls: type[BaseNodeRenderer], library_identity: Optional[LibraryIdentity] = None) -> str | None:
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
        
        # Check if this is a default renderer and register it automatically
        if renderer_cls.class_identity.is_default:
            self._default_renderer_name = registry_key
        elif self._default_renderer_name is None:
            # Automatically set as default if no default is set yet
            self._default_renderer_name = registry_key

        # Check if this is an error renderer and register it automatically
        if renderer_cls.class_identity.is_error:
            self._error_renderer = renderer_cls

        return super()._register(registry_key, renderer_cls, library_identity)

    def _unregister_class(self, registry_key: str) -> type[BaseNodeRenderer] | None:
        """Unregister a renderer by its registry_key
        Args:
            registry_key: The haywire registry_key of the renderer to unregister
        Returns:
            type[BaseNodeRenderer] | None: The unregistered renderer class or None if not found
        """
        if self._default_renderer_name == registry_key:
            if len(self.list_names()) > 0:
                self._default_renderer_name = self.list_names()[0]
            else:
                self._default_renderer_name = None
                logging.warning(f"Default renderer '{registry_key}' unregistered, no renderers left in registry")

        removed_class = super()._unregister(registry_key)
        
        if removed_class == self._error_renderer:
            self._error_renderer = None
            logging.warning(f"Error renderer '{registry_key}' unregistered, no error renderer left in registry")    
        
        return removed_class

    def get_renderer_class(self, renderer_name: str | None) -> type[BaseNodeRenderer]:
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

    def get_default_renderer(self) -> type[BaseNodeRenderer] | None:
        """Get the default renderer class"""
        if self._default_renderer_name:
            if self.has(self._default_renderer_name):
                return self._classes[self._default_renderer_name]
        return None

    def get_error_renderer(self) -> type[BaseNodeRenderer] | None:
        """Get the error renderer class"""
        return self._error_renderer