"""
Base classes for the Haywire library system
"""

from abc import ABC, abstractmethod
import sys
import importlib
import traceback
from enum import Enum
from typing import Callable, Dict, Any, Optional, Type
from pathlib import Path
import time
import logging
from dataclasses import dataclass

from haywire.core.registry.folder_scan import module_scan_for_classes
from haywire.core.registry.utils import resolve_module_name

class RegistryFolder(Enum):
    """Defines the folder names for the registries."""
    WIDGETS = 'widgets'
    RENDERERS = 'renderers'
    NODES = 'nodes'
    ADAPTERS = 'adapters'

# Required directories for a valid library structure
REQUIRED_LIB_DIRS = [RegistryFolder.WIDGETS.value,
                     RegistryFolder.RENDERERS.value,
                     RegistryFolder.NODES.value,
                     RegistryFolder.ADAPTERS.value]

HAYWIRE_CORE_LIB_NAME = 'haywire.core'

class FileEventType(Enum):
    """Enum for file change event types"""
    CREATED = 'created'
    MODIFIED = 'modified'
    DELETED = 'deleted'

@dataclass
class FileChangeEvent:
    """Represents a file change event"""
    file_path: str
    event_type: FileEventType  # 'created', 'modified', 'deleted'
    timestamp: float


@dataclass
class LibraryMetadata:
    """Metadata for a Haywire library"""
    name: str
    version: str
    description: str
    url: str
    help_url: str
    author: str
    author_url: str
    dependencies: list[str] = None
    file_watcher: bool = False  # Whether to watch for file changes
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class BaseRegistry(ABC):
    """Abstract base class for all registries"""
    
    def __init__(self):
        self._items: Dict[str, Any] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
    
    def _register(self, name: str, item: Any, metadata: Optional[Dict[str, Any]] = None):
        """Register an item with optional metadata"""
        self._items[name] = item
        if metadata:
            self._metadata[name] = metadata

    def _unregister(self, name: str) -> type[Any]:
        """Remove an item from the registry"""
        delete_item = self._items.get(name)

        if name in self._items:
            del self._items[name]
        if name in self._metadata:
            del self._metadata[name]
        
        return delete_item

    def get(self, name: str) -> Optional[Any]:
        """Get an item by name"""
        return self._items.get(name)
    
    def has(self, name: str) -> bool:
        """Check if an item is registered"""
        return name in self._items
    
    def list_names(self) -> list[str]:
        """List all registered item names"""
        return list(self._items.keys())
    
    def get_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for an item"""
        return self._metadata.get(name)


class BaseClassRegistry(BaseRegistry):
    """Abstract base class for all class registries"""
    directory_name: str = None  # To be overridden by subclasses
    class_filter: Callable[[Type], bool] = None
  
    def __init__(self):
        super().__init__()
        self._class_name: Dict[str, str] = {}  # Name of the class being registered
        self._module_to_classes: Dict[str, list[str]] = {}  # Track which classes belong to which module
     
    def _register(self, name: str, item: Any, metadata: Optional[Dict[str, Any]] = None):
        super()._register(name, item, metadata)
        self._class_name[name] = item.__name__

        # Track module to class mapping
        module_name = item.__module__
        if module_name not in self._module_to_classes:
            self._module_to_classes[module_name] = []
        if name not in self._module_to_classes[module_name]:
            self._module_to_classes[module_name].append(name)

    def _unregister(self, name: str):
        """Remove a class from the registry"""
        if name in self._class_name:
            del self._class_name[name]
        
        # Clean up module to class mapping
        for module_name, class_list in self._module_to_classes.items():
            if name in class_list:
                class_list.remove(name)
                if not class_list:  # Remove empty module entries
                    del self._module_to_classes[module_name]
                break

        return super()._unregister(name)

    @abstractmethod
    def handle_module_change(self, module: str, event: FileChangeEvent, metadata: LibraryMetadata):
        """
        Handle changes to a module by reloading and re-registering classes.
        This method should be implemented by subclasses to define specific behavior.
        """
        pass

    def _on_creation(self, model: str) -> list[type]:
        """Helps in creation of a new module by returning classes

        Args:
            model (str): The module name that has been created.
        
        Returns:
            list: List of classes that have been discovered
        """
        logging.info(f"New module '{model}' created. Scanning for classes.")
        return module_scan_for_classes(model, self.class_filter)

    def _on_change(self, module: str) -> list:
        """Handle changes to a module by reloading and re-registering classes
        
        Args:
            module (str): The module name that has changed.
        
        Returns:
            list: List of classes that need to be unregistered
        """
        logging.info(f"Reloading module '{module}' due to change.")
        # Get classes that need to be updated
        classes_to_update = self._module_to_classes.get(module, [])
        if not classes_to_update:
            logging.info(f"Module '{module}' has no classes to update.")
            return

        # Store old class info for re-registration
        old_class_info: Dict[str, str] = {}
        for class_name in classes_to_update:
            old_class_info[self._class_name[class_name]] = class_name
        
        # Remove old classes from the system
        del sys.modules[module]
 
        # Reload the module
        if module in sys.modules:
            reloaded_module = importlib.reload(sys.modules[module])
        else:
            reloaded_module = importlib.import_module(module)
        
        removed_classes = []

        # Re-register classes from reloaded module  
        for class_name in old_class_info:
            if hasattr(reloaded_module, class_name):
                self._items[old_class_info[class_name]] = getattr(reloaded_module, class_name)
                logging.info(f"Reloaded and re-registered '{old_class_info[class_name]}' with '{class_name}' from {module}")
            else:
                removed_classes.append(old_class_info[class_name])
                logging.warning(f"class '{old_class_info[class_name]}' with '{class_name}' no longer exists in reloaded module '{module}'")

        return removed_classes
    
    def _on_delete(self, module: str) -> list[str]:
        """ Helps with deletion of a module by returning all classes from it.

        Args:
            module (str): The module name that has been deleted.
        
        Returns:
            list: List of classes that need to be unregistered
        """
        logging.info(f"Module '{module}' has been deleted. Unregistering classes.")
        classes_to_delete = self._module_to_classes.get(module, [])

        return classes_to_delete

class BaseLibrary(ABC):
    """Abstract base class for all libraries"""
    
    def __init__(self, metadata: LibraryMetadata, file_path: str):
        self.metadata = metadata
        self.file_path = file_path
        self._widget_registry = None
        self._renderer_registry = None
        self._adapter_registry = None
        self._node_registry = None

    def _register_components(self, widget_registry, renderers_registry, adapter_registry, node_registry):
        """
        First: Register this global registries with the library
        Then: Let the library register its components
        """
        self._widget_registry = widget_registry
        self._renderer_registry = renderers_registry
        self._adapter_registry = adapter_registry
        self._node_registry = node_registry

        self.register_components(widget_registry, renderers_registry, adapter_registry, node_registry)

    @abstractmethod
    def register_components(self, widget_registry, renderers_registry, adapter_registry, node_registry):
        """Register this library's components with the global registries"""
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate that this library is properly structured"""
        pass

    def handle_file_change(self, event: FileChangeEvent):
        """
        Handle a file change event by determining which registry is responsible
        and triggering appropriate actions
        """
        file_path = Path(event.file_path)

        module = resolve_module_name(file_path)

        # Determine which component type this file belongs to based on directory structure
        path_parts = module.split(".")
        if len(path_parts) > 1:
            # Map directory to registry and handle the change
            if self._node_registry and self._node_registry.directory_name == path_parts[1]:
                self._node_registry.handle_module_change(module, event, self.metadata)
            elif self._widget_registry and self._widget_registry.directory_name == path_parts[1]:
                self._widget_registry.handle_module_change(module, event, self.metadata)
            elif self._adapter_registry and self._adapter_registry.directory_name == path_parts[1]:
                self._adapter_registry.handle_module_change(module, event, self.metadata)
            elif self._renderer_registry and self._renderer_registry.directory_name == path_parts[1]:
                self._renderer_registry.handle_module_change(module, event, self.metadata)



