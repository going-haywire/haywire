"""
Base classes for the Haywire library system
"""

from abc import ABC, abstractmethod
import sys
import importlib
import traceback
from enum import Enum
from typing import Callable, Dict, Any, Optional, Type
import time
import logging
from dataclasses import dataclass

from haywire.core.inventory.folder_scan import _catch_import_modules, module_scan_for_classes

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


@dataclass
class LibraryMetadata:
    """Metadata for a Haywire library"""
    label: str
    version: str
    description: str
    url: str
    help_url: str
    author: str
    author_url: str
    id: str = None  # Unique identifier for the library, defaults to label if not set
    dependencies: list[str] = None
    file_watcher: bool = False  # Whether to watch for file changes

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class BaseClassRegistry(BaseRegistry):
    """Abstract base class for all class registries"""
    directory_name: str = None  # To be overridden by subclasses
    class_filter: Callable[[Type], bool] = None
  
    def __init__(self):
        super().__init__()
        self._module_class_name: Dict[str, str] = {}  # Name of the class being registered
        self._module_to_classes: Dict[str, list[str]] = {}  # Track which classes belong to which module
     
    def _register(self, name: str, item: Any, metadata: Optional[Dict[str, Any]] = None):
        """Register a class with its name and optional metadata
        Args:
            name (str): The haywire name of the class to register
            item (Any): The class to register
            metadata (Optional[Dict[str, Any]]): Optional metadata for the class
        """
        super()._register(name, item, metadata)
        self._module_class_name[name] = item.__name__

        # Track module to class mapping
        module_name = item.__module__
        if module_name not in self._module_to_classes:
            self._module_to_classes[module_name] = []
        if name not in self._module_to_classes[module_name]:
            self._module_to_classes[module_name].append(name)

        logging.info(f"Registered class '{name}' named '{item.__name__}' from '{module_name}' has been registered.")


    def _unregister(self, name: str):
        """Remove a class from the registry
        Args:
            name (str): The haywire name of the class to unregister
        """

        logging.info(f"Unregistering class '{name}' named  '{self._module_class_name[name]}' from '{self._items[name].__module__}' ...")

        if name in self._module_class_name:
            del self._module_class_name[name]
        
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

    def _on_creation(self, module: str) -> list[type]:
        """returns all relevant classes of the module

        Args:
            module (str): The module name that has been created.

        Returns:
            list: List of relevant classes that are in this module
        """
        return module_scan_for_classes(module, self.class_filter, True)

    def _on_change(self, module_name: str) -> tuple[list, list]:
        """re-registering existing classes within the module
        and returning the classes that need to be
        additionally registered / unregistered

        Args:
            module_name (str): The module name that has changed.
        
        Returns:
            [list,list]: [(List of classes to be registered), (List of haywire class names to be unregistered)]
        """
        logging.info(f"Reloading module '{module_name}' due to change...")
        # Get all classes in this module
        classes_to_add = module_scan_for_classes(module_name, self.class_filter, True)
        hw_class_names_to_remove = []

        # Get registered classes from this module that need to be updated
        hw_class_names_to_update = self._module_to_classes.get(module_name, [])
        if hw_class_names_to_update:

            # Store old class info for re-registration
            mod_to_hw_class_name_mapping: Dict[str, str] = {} # key: module class name, value: haywire class name
            for mod_class_name in hw_class_names_to_update:
                mod_to_hw_class_name_mapping[self._module_class_name[mod_class_name]] = mod_class_name
                # check if the registered old class name matches a class name in the new module
                class_to_remove = next((cls for cls in classes_to_add if cls.__name__ == self._module_class_name[mod_class_name]), None)
                if class_to_remove:
                    # Remove the class from the list to avoid re-registering it
                    classes_to_add.remove(class_to_remove)
                
            # this gets the module that has already been forcefully reloaded
            # by the module_scan_for_classes function

            module = _catch_import_modules(module_name)
            
            # Re-register classes from reloaded module  
            for mod_class_name in mod_to_hw_class_name_mapping:
                if hasattr(module, mod_class_name):
                    self._items[mod_to_hw_class_name_mapping[mod_class_name]] = getattr(module, mod_class_name)
                    logging.info(f"... Re-loaded and re-registered: '{mod_to_hw_class_name_mapping[mod_class_name]}' with '{mod_class_name}' from {module_name}")
                else:
                    hw_class_names_to_remove.append(mod_to_hw_class_name_mapping[mod_class_name])
        
        else:
            logging.info(f"Module '{module_name}' has no matching classes that need an update.")

        return classes_to_add, hw_class_names_to_remove.copy()

    def _on_delete(self, module: str) -> list[str]:
        """Marks the classes need to be unregistered.

        Args:
            module (str): The module name that has been deleted.
        
        Returns:
            list: List of haywire class names that need to be unregistered
        """
        logging.info(f"Module '{module}' has been deleted. Unregistering classes.")
        classes_to_delete = self._module_to_classes.get(module, [])

        return classes_to_delete.copy()





