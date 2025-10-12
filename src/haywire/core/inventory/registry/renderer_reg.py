import logging
from typing import Any, Dict, Optional, TypeVar, Union

from ..metadata import LibraryMetadata
from haywire.core.ui.base_renderer import BaseNodeRenderer, is_renderer

from ..base import BaseClassRegistry, FileChangeEvent, FileEventType, RegistryFolder
from ..utils import camel_to_dot_case, reg_key

class RendererRegistry(BaseClassRegistry):
    """Registry for NodeRenderer classes with fallback support"""
    directory_name: str = RegistryFolder.RENDERERS.value
    class_filter = lambda self, cls: is_renderer(cls)  # Use the renderer filter

    def __init__(self):
        super().__init__()
        self._default_renderer_name: str | None = None
        self._error_renderer: type | None = None

    def register_renderer(self, renderer_cls: type[BaseNodeRenderer], metadata: Optional[Dict[str, Any]] = None):
        """
        Register a renderer class.

        Args:
            name: Unique name for the renderer
            renderer_class: The NodeRenderer class
            metadata: Optional metadata for the renderer
        """

        registry_key = reg_key(metadata.id, renderer_cls.class_identity.registry_id)

        self._register(registry_key, renderer_cls, metadata)

        # Automatically set as default if no default is set yet
        if self._default_renderer_name is None:
            self._default_renderer_name = registry_key

    def unregister_renderer(self, name: str) -> type[BaseNodeRenderer] | None:
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

    def register_default_renderer(self, renderer_cls: type[BaseNodeRenderer]):
        """Register the default renderer by class"""

        # get the widget name from the class
        # This assures to work even it the widget class was removed from the registry
        renderer_name = next((name for name, cls in self._items.items() if cls == renderer_cls), None)

        if renderer_name:
            self._default_renderer_name = renderer_name
        else:
            logging.warning(f"Renderer class '{renderer_cls.__name__}' not found in registry, cannot set as default")

    def register_error_renderer(self, renderer_class: type[BaseNodeRenderer]):
        """Register the error renderer class"""
        self._error_renderer = renderer_class

    def handle_module_change(self, module: str, event: FileChangeEvent, metadata: LibraryMetadata):
        """
        Handle file change events for node modules.

        Args:
            event: FileChangeEvent containing file path and event type
        """
        if event.event_type == FileEventType.CREATED:
            added_classes = self._on_creation(module)
            if added_classes:
                for cls_name in added_classes:
                    self.register_renderer(cls_name, metadata)
        elif event.event_type == FileEventType.MODIFIED:
            added_classes, removed_classes = self._on_change(module)
            if removed_classes:
                for cls_name in removed_classes:
                    self.unregister_renderer(cls_name)
            if added_classes:
                for cls_name in added_classes:
                    self.register_renderer(cls_name, metadata)
        elif event.event_type == FileEventType.DELETED:
            removed_classes = self._on_delete(module)
            if removed_classes:
                for cls_name in removed_classes:
                    self.unregister_renderer(cls_name)


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