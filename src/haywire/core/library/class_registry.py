"""
Base classes for the Haywire library system
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import importlib
from pathlib import Path
import sys
from typing import Callable, Dict, Any, Optional, Type, List, Tuple
import logging

from .library_identity import LibraryIdentity
from .dependency_graph import DependencyGraph, ReloadPlan
from .folder_scan import FolderScanMixin
from ..errors import log_detailed_error

HAYWIRE_CORE_LIB_NAME = 'haywire.core'

# Type alias for customer callbacks
CustomerCallback = Callable[[str, List[str], LibraryIdentity], None]


class FileEventType(Enum):
    """Enum for file change event types"""
    CREATED = 'creation'
    MODIFIED = 'modification'
    DELETED = 'deletion'
    DETECTED = 'detection'

@dataclass
class FileChangeEvent:
    """Represents a file change event"""
    file_path: str
    event_type: FileEventType  # 'created', 'modified', 'deleted', 'detected'
    library_identity: LibraryIdentity
    timestamp: float

class HotReloadRegistry(ABC):
    """Abstract base class for registries that support hot-reloading"""
    
    @abstractmethod
    def event_dispatcher(self, event: FileChangeEvent):
        """Handle creation of a module"""
        pass

class BaseClassRegistry(HotReloadRegistry, FolderScanMixin):
    """Abstract base class for all class registries"""
  
    def __init__(self):
        # Registry functionality moved from BaseRegistry
        self._classes: Dict[str, Any] = {} # registry_key -> class
        
        # BaseClassRegistry specific attributes
        self._module_class_name: Dict[str, str] = {}  # Name of the class being registered
        self._module_to_classes: Dict[str, list[str]] = {}  # Track which classes belong to which module
        self._dependency_graph = DependencyGraph() # For hot-reload dependency tracking
        self._registered_folders: Dict[str, LibraryIdentity] = {} # folder_path -> library_identity
        
        # Hot reload callback management
        self._customer_callbacks: List[CustomerCallback] = []  # Direct consumers (factories, etc.)
        self._registry_subscribers: List[HotReloadRegistry] = []  # Other registries that depend on this one

    @abstractmethod
    def _class_filter(self, cls: Type) -> bool:
        """Function that returns True if a class should be included in this registry"""
        pass

    @abstractmethod
    def _register_class(self, cls: Type, library_identity: LibraryIdentity) -> str | None:
        """Register a class with its library metadata"""
        pass

    @abstractmethod
    def _unregister_class(self, registry_key: str) -> type[Any] | None: 
        """Unregister a class by its registry_key"""
        pass

    # ============================================================================
    # Core Registry (Pure State Management)
    # ============================================================================

    def get(self, registry_key: str) -> Any | None:
        """Retrieve a registered class by its haywire registry_key"""
        return self._classes.get(registry_key)  

    def has(self, registry_key: str) -> bool:
        """Check if a class is registered"""
        return registry_key in self._classes

    def list_names(self) -> list[str]:
        """List all registered class names"""
        return list(self._classes.keys())

    def _register(self, registry_key: str, cls: Any, library_identity: Optional[LibraryIdentity] = None) -> str | None:
        """
        Register a class with its name and optional metadata
        Args:
            registry_key (str): The haywire registry_key of the class to register
            cls (Any): The class to register
            library_identity (Optional[LibraryIdentity]): The library identity to associate with the class
        Returns:
            str: The haywire registry_key of the registered class
        """
        # Set the registry_key in the class_identity if it exists
        if hasattr(cls, 'class_identity'):
            cls.class_identity.registry_key = registry_key
        else:
            raise ValueError(f"Library '{library_identity.label}': Class {cls} does not have a class_identity attribute. Cannot register. This is likely due to a missing condition in the implementation of the registry's class filter method.")

        # Check for duplicates
        if self.has(registry_key):
            raise ValueError(f"Library '{library_identity.label}': Attempt to register Node '{cls.class_identity.label}' under an existing registry_key '{registry_key}'. This is not allowed. Indication of double use of a node registry_id.")

        # Store the library identity as class attributes 
        cls.class_library = library_identity

        # Register the class
        self._classes[registry_key] = cls

        self._module_class_name[registry_key] = cls.__name__

        # Track module to class mapping
        module_name = cls.__module__
        if module_name not in self._module_to_classes:
            self._module_to_classes[module_name] = []
        if registry_key not in self._module_to_classes[module_name]:
            self._module_to_classes[module_name].append(registry_key)

        return registry_key

    def _unregister(self, registry_key: str) -> type[Any] | None:
        """
        Remove a class from the registry
        Args:
            registry_key (str): The haywire registry_key of the class to unregister
        Returns:
            type[Any] | None: The unregistered class, or None if not found
        """
        if registry_key in self._module_class_name:
            del self._module_class_name[registry_key]
        
        # Clean up module to class mapping
        for module_name, class_list in self._module_to_classes.items():
            if registry_key in class_list:
                class_list.remove(registry_key)
                if not class_list:  # Remove empty module entries
                    del self._module_to_classes[module_name]
                break

        # Remove from registry 
        delete_cls = self._classes.get(registry_key)
        if registry_key in self._classes:
            del self._classes[registry_key]
        return delete_cls

    # ============================================================================
    # Folder-Aware Registry (File System Integration)
    # ============================================================================

    def add_folder(self, folder_path: str, library_identity: LibraryIdentity, exclude_patterns: Optional[list[str]] = None):
        """
        Initial scan of the folder for classes matching the registry's class filter
        and add them to this registry.
        
        This method is called by the library when it is enabled.

        Args:
            folder_path (str): Path to the folder to scan
            exclude_patterns (Optional[list[str]]): List of filename patterns to exclude
        """
        if folder_path in self._registered_folders:
            logging.warning(
                f"Library '{library_identity.label}': Folder "
                f"'{folder_path[len(library_identity.folder_path):]}' is already registered "
                f"in registry '{self.__class__.__name__}'. Skipping.")
            return
        
        self._registered_folders[folder_path] = library_identity

        logging.info(
            f"Library '{library_identity.label}': START Scanning folder "
            f"'{folder_path[len(library_identity.folder_path):]}' for files to register classes...")

        file_paths = self.folder_scan_for_pyfiles(folder_path, exclude_patterns)

        for file_path in file_paths:
            try:
                if self._validate_python_file(file_path):
                    module_name = self.resolve_module_name(
                        file_path, 
                        library_identity.folder_path,
                        library_identity.module_name
                    )
                    self._on_creation(module_name, library_identity)

            except Exception as e:
                try:
                    rel_path = folder_path[len(library_identity.folder_path):]
                    log_detailed_error(
                        exception=e,
                        operation="Registry folder import",
                        module_name=locals().get('module_name', 'unknown'),
                        message=f"Failed while importing folder '...{rel_path}' in library '{library_identity.label}'",
                        library_identity=library_identity
                    )
                except Exception as logging_error:
                    logging.error(
                        f"Library '{library_identity.label}': "
                        f"Failed notifying registry : {e}")

        logging.info(
            f"Library '{library_identity.label}': ... Scanning folder -> DONE. "
            f"{len(file_paths)} files processed.")

    def remove_folder(self, folder_path: str, library_identity: LibraryIdentity, exclude_patterns: Optional[list[str]] = None):
        """ 
        Remove all classes associated with a library_identity from this registry.
        This method is called by the library when it is disabled.

        Args:
            folder_path (str): Path to the folder to remove
            exclude_patterns (Optional[list[str]]): List of filename patterns to exclude
        """
        del self._registered_folders[folder_path]

        file_paths = self.folder_scan_for_pyfiles(folder_path, exclude_patterns)

        for file_path in file_paths:
            try:
                module_name = self.resolve_module_name(
                    file_path,
                    library_identity.folder_path,
                    library_identity.module_name
                )
                self._on_delete(module_name, library_identity)

            except Exception as e:
                try:
                    rel_path = folder_path[len(library_identity.folder_path):]
                    log_detailed_error(
                        exception=e,
                        operation="Registry folder import",
                        module_name=locals().get('module_name', 'unknown'),
                        message=f"Failed while importing folder '...{rel_path}' in library '{library_identity.label}'",
                        library_identity=library_identity
                    )
                except Exception as logging_error:
                    logging.error(
                        f"Library '{library_identity.label}': "
                        f"Failed notifying registry : {e}")

    # ============================================================================
    # Hot-Reload Registry (Reload Orchestration)
    # ============================================================================

    def event_dispatcher(self, event: FileChangeEvent):
        """
        Dispatch file change events to the appropriate handlers based on event type.

        This method is called by the file watcher when a file change is detected.

        Args:
            event (FileChangeEvent): The file change event to handle
        """
        try:
            # Skip validation for deleted files
            logging.info(
                f"Library '{event.library_identity.label}': "
                f"DETECTED Hot Reloading event: file-'{event.event_type.value}' "
                f"on file: {event.file_path[len(event.library_identity.folder_path):]}. "
                f"INITIATING ...")
            
            # no need to validate deleted files
            if event.event_type != FileEventType.DELETED:
                if not self._validate_python_file(event.file_path):
                    logging.error(
                        f"Library '{event.library_identity.label}': "
                        f"Invalid Python file: {event.file_path}. Skipping Hot Reloading.")
                    return None
            
            file_path = Path(event.file_path)
            module_name = self.resolve_module_name(
                file_path,
                event.library_identity.folder_path,
                event.library_identity.module_name
            )
            
            if event.event_type == FileEventType.CREATED:
                self._on_creation(module_name, event.library_identity)
            elif event.event_type == FileEventType.MODIFIED:
                if module_name in sys.modules:
                    self._on_change(module_name, event.library_identity)
                else:
                    # covering an edge case where a module is modified but not yet loaded
                    logging.info(f"Library '{event.library_identity.label}': Module '{module_name}' not found in sys.modules. Creating new module.")
                    self._on_creation(module_name, event.library_identity)
            elif event.event_type == FileEventType.DELETED:
                self._on_delete(module_name, event.library_identity)

            logging.info(
                f"Library '{event.library_identity.label}': "
                f"...Hot Reloading -> DONE.")
            
            # Notify registry subscribers after successful reload
            self._notify_registry_subscribers(event)

        except Exception as e:
            try:
                log_detailed_error(
                    exception=e,
                    operation="Registry Hotreload Callback",
                    module_name=locals().get('module_name', 'unknown'),
                    message=f"Failed notifying registry about file {event.event_type.value} in library '{event.library_identity.label}'",
                    library_identity=event.library_identity
                )
                # TODO: emit event for failed import
            except Exception as logging_error:
                logging.error(
                    f"Library '{event.library_identity.label}': "
                    f"Failed notifying registry on file:{event.file_path}' : {e}")
            
            logging.error(
                f"Library '{event.library_identity.label}': "
                f"...Hot Reloading on file on file: {event.file_path} -> FAILED.")
         

    def _on_creation(self, module_name: str, library_identity: LibraryIdentity):
        """called when a new module is created / loaded
        Args:
            module (str): The module name that has been created.
        Returns:
            list: List of relevant classes that are in this module
        """
        if module_name is None:
            return  # Skip processing if validation failed

        added_classes, _ = self.module_scan_for_classes(module_name, library_identity, self._class_filter, True)
        if added_classes:
            # This module contains managed classes - track it with scope prefix
            # Scope prefix limits which dependencies are tracked (prevents tracking parent classes)
            self._dependency_graph.add_managed_module(module_name, library_identity.module_name)
            
            for cls in added_classes:
                self._register_class(cls, library_identity)
                #TODO: emit event for added class

    
    def _on_change(self, module_name: str, library_identity: LibraryIdentity):
        """
        re-registering existing classes within the module
        and returning the classes that need to be
        additionally registered / unregistered
        Args:
            module_name (str): The module name that has changed.
        Returns:
            [list,list]: [(List of classes to be registered), (List of haywire class names to be unregistered)]
        """
        if module_name is None:
            return  # Skip processing if validation failed

        logging.info(
            f"Library '{library_identity.label}': Analyzing dependencies for "
            f"changed module '{module_name}'..."
        )
        
        # Get reload plan from dependency graph
        reload_plan = self._dependency_graph.get_reload_plan(module_name)
        
        logging.info(
            f"Library '{library_identity.label}': Reload plan: "
            f"{len(reload_plan.non_managed_modules)} helpers, "
            f"{len(reload_plan.managed_modules)} managed classes"
        )
        
        # Step 1: Reload non-managed helper modules first
        for helper_module in reload_plan.non_managed_modules:
            if helper_module in sys.modules:
                logging.info(
                    f"Library '{library_identity.label}': Reloading helper "
                    f"module '{helper_module}'..."
                )
                importlib.reload(sys.modules[helper_module])
        
        # Step 2: Reload managed modules using registry's special handling
        for managed_module in reload_plan.managed_modules:
            logging.info(
                f"Library '{library_identity.label}': Reloading managed "
                f"module '{managed_module}'..."
            )
            self._reload_managed_module(managed_module, library_identity)

    def _reload_managed_module(self, module_name: str, library_identity: LibraryIdentity):
        """
        Reload a single managed module with registry-specific handling.
        Called by the _on_change method.
        """

        # Create snapshot before reload
        snapshot = self._create_rollback_snapshot(module_name)

        # if anything goes wrong, we can rollback to this snapshot
        try:
            # Get all classes in this module
            classes_to_add, module = self.module_scan_for_classes(module_name, library_identity=library_identity, class_filter=self._class_filter, force_reload=True)
            class_names_to_remove = []
            # Simple container for old/new class pairs

            classes_to_reload: List[Tuple[Type[Any], Type[Any]]] = []

            # Get registered classes from this module that need to be updated
            class_names_to_update = self._module_to_classes.get(module_name, [])
            if class_names_to_update:

                # Store old class info for re-registration
                mod_to_class_name_mapping: Dict[str, str] = {} # module class name -> haywire class name
                for mod_class_name in class_names_to_update:
                    mod_to_class_name_mapping[self._module_class_name[mod_class_name]] = mod_class_name
                    # check if the registered old class name matches a class name in the new module
                    class_to_remove = next((cls for cls in classes_to_add if cls.__name__ == self._module_class_name[mod_class_name]), None)
                    if class_to_remove:
                        # Remove the class from the list to avoid re-registering it
                        classes_to_add.remove(class_to_remove)
                    
                # Re-register classes from reloaded module  
                for mod_class_name in mod_to_class_name_mapping:
                    if hasattr(module, mod_class_name):
                        # to update a class, we need to unregister the old one and register the new one
                        new_class: Type[Any] = getattr(module, mod_class_name)
                        old_class_name = mod_to_class_name_mapping[mod_class_name]
                        classes_to_reload.append((old_class_name, new_class))
                    else:
                        class_names_to_remove.append(mod_to_class_name_mapping[mod_class_name])
            
            cls_names_to_remove = class_names_to_remove.copy()
            
            # If we have an exception during re-registration, but we got so far
            # we need to rollback AND re-register all classes from the snapshot
            if snapshot:
                snapshot['needs_reregistring'] = True

            if classes_to_reload:
                for old_cls_name, new_cls in classes_to_reload:
                    self._unregister_class(old_cls_name)
                    new_key = self._register_class(new_cls, library_identity)
                    logging.info(
                        f"Library '{library_identity.label}': "
                        f"...Re-loaded and re-registered from {module_name}")
                    # Notify customer callbacks about reloaded class
                    if new_key:
                        self._notify_customer_callbacks(
                            registry_key=new_key,
                            affected_class_names=[new_cls.__name__],
                            library_identity=library_identity
                        )
            if cls_names_to_remove:
                for cls_name in cls_names_to_remove:
                    removed_cls = self._unregister_class(cls_name)
                    # Notify customer callbacks about removed class
                    if removed_cls:
                        self._notify_customer_callbacks(
                            registry_key=cls_name,
                            affected_class_names=[removed_cls.__name__],
                            library_identity=library_identity
                        )
            if classes_to_add:
                for cls in classes_to_add:
                    new_key = self._register_class(cls, library_identity)
                    # Notify customer callbacks about added class
                    if new_key:
                        self._notify_customer_callbacks(
                            registry_key=new_key,
                            affected_class_names=[cls.__name__],
                            library_identity=library_identity
                        )

        except Exception as e:
            logging.error(
                f"Library '{library_identity.label}': "
                f"Reload failed for '{module_name}': {e}")
            self._rollback_snapshot(module_name, snapshot, library_identity)            
            raise       

    def _on_delete(self, module_name: str, library_identity: LibraryIdentity):
        """Called when a module is deleted or unloaded.
        Args:
            module (str): The module name that has been deleted.
        """
        if module_name is None:
            return  # Skip processing if validation failed (shouldn't happen for DELETE events)
        
        classes_to_delete = self._module_to_classes.get(module_name, [])
        removed_classes = classes_to_delete.copy()
    
        if removed_classes:
            for cls_name in removed_classes:
                self._unregister_class(cls_name)
                #TODO: emit event for removed class
        
        # Remove from dependency graph if no more managed classes
        if not self._module_to_classes.get(module_name):
            self._dependency_graph.remove_managed_module(module_name)

    # ============================================================================
    # Snapshot Registry (Rollback Support)
    # ============================================================================

    def _create_rollback_snapshot(self, module_name: str) -> Optional[Dict[str, Any]]:
        """Create snapshot of module state for rollback"""
        if module_name not in sys.modules:
            return None
        
        module = sys.modules[module_name]
        snapshot = {
            'module': module,
            'needs_reregistring': False,
            'registered_classes': {}
        }
        
        # Snapshot registered classes from this module
        for hw_name in self._module_to_classes.get(module_name, []):
            snapshot['registered_classes'][hw_name] = {
                'class': self._classes.get(hw_name),
                'class_name': self._module_class_name.get(hw_name)
            }
        
        return snapshot
 
    def _rollback_snapshot(self, module_name: str, snapshot: Dict[str, Any], library_identity: LibraryIdentity):
        """Restore module from snapshot after failed reload"""            
        if snapshot:
            # Restore module in sys.modules
            sys.modules[module_name] = snapshot['module']
            
            if snapshot['needs_reregistring']:
                # Re-register classes from snapshot
                for hw_name, class_info in snapshot['registered_classes'].items():
                    self._unregister_class(hw_name.class_identity.registry_key)
                    self._register_class(class_info['class'], library_identity)
            
            logging.info(
                f"Library '{library_identity.label}': "
                f"Rollback complete for '{module_name}'")

    # ============================================================================
    # Hot Reload Callback Management
    # ============================================================================
    
    def add_customer_callback(self, callback: CustomerCallback) -> None:
        """
        Register a customer callback to be notified of hot reload events.
        
        Customer callbacks are invoked immediately after a class is reloaded,
        added, or removed. They receive the registry key and affected class names.
        
        Args:
            callback: Function to call on hot reload events with signature:
                     (registry_key: str, affected_class_names: List[str], 
                      library_identity: LibraryIdentity) -> None
        """
        if callback not in self._customer_callbacks:
            self._customer_callbacks.append(callback)
            logging.debug(f"Registered customer callback: {callback.__name__}")
    
    def remove_customer_callback(self, callback: CustomerCallback) -> None:
        """
        Unregister a customer callback.
        
        Args:
            callback: The callback to remove
        """
        if callback in self._customer_callbacks:
            self._customer_callbacks.remove(callback)
            logging.debug(f"Removed customer callback: {callback.__name__}")
    
    def add_registry_subscriber(self, registry: HotReloadRegistry) -> None:
        """
        Register another registry to be notified of hot reload events.
        
        Registry subscribers are invoked after customer callbacks and receive
        complete FileChangeEvent information for their own processing.
        
        Args:
            registry: Another registry that needs to react to changes in this registry
        """
        if registry not in self._registry_subscribers:
            self._registry_subscribers.append(registry)
            logging.debug(f"Registered registry subscriber: {registry.__class__.__name__}")
    
    def remove_registry_subscriber(self, registry: HotReloadRegistry) -> None:
        """
        Unregister a registry subscriber.
        
        Args:
            registry: The registry to unsubscribe
        """
        if registry in self._registry_subscribers:
            self._registry_subscribers.remove(registry)
            logging.debug(f"Removed registry subscriber: {registry.__class__.__name__}")
    
    def _notify_customer_callbacks(self, registry_key: str, 
                                   affected_class_names: List[str],
                                   library_identity: LibraryIdentity) -> None:
        """
        Notify all customer callbacks about a hot reload event.
        
        This method is called internally during hot reload operations.
        Errors in individual callbacks are logged but don't stop other callbacks.
        
        Args:
            registry_key: The registry key affected
            affected_class_names: List of class names modified
            library_identity: The library where the change occurred
        """
        for callback in self._customer_callbacks:
            try:
                callback(registry_key, affected_class_names, library_identity)
            except Exception as e:
                logging.error(
                    f"Customer callback '{callback.__name__}' failed for registry_key '{registry_key}': {e}",
                    exc_info=True
                )
    
    def _notify_registry_subscribers(self, event: FileChangeEvent) -> None:
        """
        Notify all registry subscribers about a hot reload event.
        
        This method is called after customer callbacks have been notified.
        Registry subscribers receive the complete event information and can
        perform their own dependency analysis and reloading.
        
        Args:
            event: The file change event that triggered the reload
        """
        for registry in self._registry_subscribers:
            try:
                registry.event_dispatcher(event)
            except Exception as e:
                logging.error(
                    f"Registry subscriber '{registry.__class__.__name__}' callback failed for {event.file_path}: {e}",
                    exc_info=True
                )
