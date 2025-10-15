"""
Base classes for the Haywire library system
"""

from abc import ABC, abstractmethod
from enum import Enum
import importlib
from pathlib import Path
import traceback
from typing import Callable, Dict, Any, Optional, Type
import logging
import ast
from dataclasses import dataclass

from ..inventory.library_identity import LibraryIdentity
from ..inventory.folder_scan import FolderScanMixin
from ..errors import log_detailed_error

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
    library_identity: LibraryIdentity
    timestamp: float


class BaseRegistry(ABC):
    """Abstract base class for all registries"""
    
    def __init__(self):
        self._items: Dict[str, Any] = {}
    
    def _register(self, name: str, item: Any):
        """Register an item with optional metadata"""
        self._items[name] = item

    def _unregister(self, name: str) -> type[Any]:
        """Remove an item from the registry"""
        delete_item = self._items.get(name)

        if name in self._items:
            del self._items[name]
        
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

class HotReloadRegistry(ABC):
    """Abstract base class for registries that support hot-reloading"""
    
    @abstractmethod
    def event_dispatcher(self, event: FileChangeEvent):
        """Handle creation of a module"""
        pass

class BaseClassRegistry(BaseRegistry, HotReloadRegistry, FolderScanMixin):
    """Abstract base class for all class registries"""
  
    def __init__(self):
        super().__init__()
        self._module_class_name: Dict[str, str] = {}  # Name of the class being registered
        self._module_to_classes: Dict[str, list[str]] = {}  # Track which classes belong to which module
     
    def _register(self, name: str, item: Any):
        """Register a class with its name and optional metadata
        Args:
            name (str): The haywire name of the class to register
            item (Any): The class to register
            metadata (Optional[Dict[str, Any]]): Optional metadata for the class
        """
        super()._register(name, item)
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
    def _class_filter(self, cls: Type) -> bool:
        """Function that returns True if a class should be included in this registry"""
        pass

    def add_folder(self, folder_path: str, library_identity: LibraryIdentity, exclude_patterns: Optional[list[str]] = None):
        """Initial scan of the folder for classes matching the registry's class filter
        and add them to this registry.

        This should be called once when the library is first loaded.

        Args:
            folder_path (str): Path to the folder to scan
            exclude_patterns (Optional[list[str]]): List of filename patterns to exclude
        """
        try:
            module_names = self.folder_scan_for_modules(folder_path, exclude_patterns)

            for module_name in module_names:
                self._on_creation(module_name, library_identity)
                
        except Exception as e:
            try:
                rel_path = folder_path[len(library_identity.folder_path):]
                log_detailed_error(
                    exception=e,
                    operation="Registry folder import",
                    module_name=locals().get('module_name', 'unknown'),
                    message=f"Failed while importing folder '..{rel_path}' in library '{library_identity.label}'",
                    library_identity=library_identity
                )
            except Exception as logging_error:
                logging.error(f"Failed notifying registry for '{library_identity.label}': {e}")
                logging.error(f"Error logging failed: {logging_error}")
    
    def event_dispatcher(self, event: FileChangeEvent):
        """
        Dispatch file change events to the appropriate handlers based on event type.

        This is called by the file watcher when a file change is detected.

        Args:
            event (FileChangeEvent): The file change event to handle
        """
        try:
            # Skip validation for deleted files
            if event.event_type != FileEventType.DELETED:
                if not self._validate_python_file(event.file_path):
                    logging.error(f"Invalid Python file: {event.file_path}. Skipping Hot Reloading.")
                    return None
            
            file_path = Path(event.file_path)
            module_name = self.resolve_module_name(file_path)

            if event.event_type == FileEventType.CREATED:
                self._on_creation(module_name, event.library_identity)
            elif event.event_type == FileEventType.MODIFIED:
                self._on_change(module_name, event.library_identity)
            elif event.event_type == FileEventType.DELETED:
                self._on_delete(module_name, event.library_identity)

        except Exception as e:
            try:
                log_detailed_error(
                    exception=e,
                    operation="Registry hotreload callback",
                    module_name=locals().get('module_name', 'unknown'),
                    message=f"Failed notifying registry about file change in library '{event.library_identity.label}'",
                    library_identity=event.library_identity
                )
            except Exception as logging_error:
                logging.error(f"Failed notifying registry on file:{event.file_path} for library:'{event.library_identity.label}': {e}")
                logging.error(f"Error logging failed: {logging_error}")
         

    def _on_creation(self, module_name: str, library_identity: LibraryIdentity):
        """returns all relevant classes of the module

        Args:
            module (str): The module name that has been created.

        Returns:
            list: List of relevant classes that are in this module
        """
        if module_name is None:
            return  # Skip processing if validation failed
            
        added_classes = self.module_scan_for_classes(module_name, library_identity, self._class_filter, True)
        if added_classes:
            for cls in added_classes:
                self._register(cls, library_identity)

    def _on_change(self, module_name: str, library_identity: LibraryIdentity):
        """re-registering existing classes within the module
        and returning the classes that need to be
        additionally registered / unregistered

        Args:
            module_name (str): The module name that has changed.
        
        Returns:
            [list,list]: [(List of classes to be registered), (List of haywire class names to be unregistered)]
        """
        if module_name is None:
            return  # Skip processing if validation failed

        logging.info(f"Reloading module '{module_name}' due to change...")
        # Get all classes in this module
        classes_to_add = self.module_scan_for_classes(module_name, library_identity=library_identity, class_filter=self._class_filter, force_reload=True)
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

            module = importlib.import_module(module_name)
            
            # Re-register classes from reloaded module  
            for mod_class_name in mod_to_hw_class_name_mapping:
                if hasattr(module, mod_class_name):
                    # to update a class, we need to unregister the old one and register the new one
                    classes_to_add.append(getattr(module, mod_class_name))
                    hw_class_names_to_remove.append(mod_to_hw_class_name_mapping[mod_class_name])
                    logging.info(f"... Re-loaded and re-registered: '{mod_to_hw_class_name_mapping[mod_class_name]}' with '{mod_class_name}' from {module_name}")
                else:
                    hw_class_names_to_remove.append(mod_to_hw_class_name_mapping[mod_class_name])
        
        else:
            logging.info(f"Module '{module_name}' has no matching classes that need an update.")

        removed_classes = hw_class_names_to_remove.copy()

        if removed_classes:
            for cls_name in removed_classes:
                self._unregister(cls_name)
        if classes_to_add:
            for cls in classes_to_add:
                self._register(cls, library_identity)

    def _on_delete(self, module_name: str, library_identity: LibraryIdentity):
        """Marks the classes need to be unregistered.

        Args:
            module (str): The module name that has been deleted.
        
        Returns:
            list: List of haywire class names that need to be unregistered
        """
        if module_name is None:
            return  # Skip processing if validation failed (shouldn't happen for DELETE events)

        logging.info(f"Module '{module_name}' has been deleted. Unregistering classes.")
        classes_to_delete = self._module_to_classes.get(module_name, [])

        removed_classes = classes_to_delete.copy()
    
        if removed_classes:
            for cls_name in removed_classes:
                self._unregister(cls_name)





