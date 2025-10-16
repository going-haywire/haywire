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

    def _register(self, renderer_cls: type[BaseNodeRenderer], library_identity: Optional[LibraryIdentity] = None) -> str | None:
        """
        Register a renderer class.

        Args:
            name: Unique name for the renderer
            renderer_class: The NodeRenderer class
            metadata: Optional metadata for the renderer
        """
        registry_key = reg_key(library_identity.id, renderer_cls.class_identity.registry_id)
        
        # Check if this is a default renderer and register it automatically
        if hasattr(renderer_cls, 'class_identity') and renderer_cls.class_identity.is_default:
            self._default_renderer_name = registry_key
        elif self._default_renderer_name is None:
            # Automatically set as default if no default is set yet
            self._default_renderer_name = registry_key

        # Check if this is an error renderer and register it automatically
        if hasattr(renderer_cls, 'class_identity') and renderer_cls.class_identity.is_error:
            self._error_renderer = renderer_cls

        return super()._register(registry_key, renderer_cls, library_identity)

    def _unregister(self, name: str) -> type[BaseNodeRenderer] | None:
        """Unregister a renderer by its haywire name
        Args:
            name: The haywire name of the renderer to unregister
        """
        if self._default_renderer_name == name:
            if self.list_names.length > 0:
                self._default_renderer_name = self.list_names[0]
            else:
                self._default_renderer_name = None
                logging.warning(f"Default renderer '{name}' unregistered, no renderers left in registry")

        removed_class = super()._unregister(name)
        
        if removed_class == self._error_renderer:
            self._error_renderer = None
            logging.warning(f"Error renderer '{name}' unregistered, no error renderer left in registry")    
        
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
            return self.get(renderer_name)

        # 2. Use default if no renderer name is specified
        if renderer_name is None and self._default_renderer_name:
            if self.has(self._default_renderer_name):
                return self.get(self._default_renderer_name)

        # 3. Return error renderer if exact renderer doesn't exist
        if self._error_renderer:
            return self._error_renderer

        # Fallback if no error renderer registered
        raise RuntimeError(f"No renderer found for '{renderer_name}' and no error renderer registered")

    def get_default_renderer(self) -> type[BaseNodeRenderer] | None:
        """Get the default renderer class"""
        if self._default_renderer_name:
            if self.has(self._default_renderer_name):
                return self.get(self._default_renderer_name)
        return None

    def get_error_renderer(self) -> type[BaseNodeRenderer] | None:
        """Get the error renderer class"""
        return self._error_renderer