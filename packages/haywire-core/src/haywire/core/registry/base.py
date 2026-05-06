"""
Base classes for the Haywire library system
"""

from typing import Dict, Any, Optional, Type, List, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass, field as dc_field
from enum import Enum
import importlib
from pathlib import Path
import sys
import logging

from ..errors import HaywireException
from ..library.identity import LibraryIdentity
from .dependency_graph import DependencyGraph
from .folder_scan import FolderScanMixin
from .lifecycle_event import LifeCycleEvent, LifeCycleEventType, LifeCycleBatchCallback

logger = logging.getLogger(__name__)


class FileEventType(Enum):
    """Enum for file change event types"""

    CREATED = "creation"
    MODIFIED = "modification"
    DELETED = "deletion"
    DETECTED = "detection"


@dataclass
class FileChangeEvent:
    """Represents a file change event"""

    file_path: str
    event_type: FileEventType  # 'created', 'modified', 'deleted', 'detected'
    library_identity: LibraryIdentity
    timestamp: float
    reloaded_modules: set[str] = dc_field(default_factory=set)
    """Track modules already reloaded in this event chain"""
    dependency_event: bool = False  # Whether this event is due to dependency reload
    """indicates if this event is a result of a dependency change (detected by a different registry)"""


class HotReloadRegistry(ABC):
    """Abstract base class for registries that support hot-reloading"""

    @abstractmethod
    def event_dispatcher(self, event: FileChangeEvent):
        """Handle creation of a module"""
        pass


class BaseRegistry(HotReloadRegistry, FolderScanMixin):
    """
    Abstract base class for all class registries

    """

    def __init__(self):
        self._dependency_graph = DependencyGraph()  # For hot-reload dependency tracking

        self._classes: Dict[str, Any] = {}  # registry_key -> class

        # stores the last life-cycle event for each class that has been processed
        # it keeps track of what was the last event type for each class,
        # even those that have been removed
        # registry_key -> event
        self._regkey_to_last_lifecycle_event: Dict[str, LifeCycleEvent] = {}

        # BaseClassRegistry specific attributes
        self._regkey_to_class_name: Dict[str, str] = {}  # registry_key -> class name
        # module -> list of registry_keys
        self._module_to_registry_keys: Dict[str, list[str]] = {}
        # folder_path -> library_identity
        self._folder_to_library: Dict[str, LibraryIdentity] = {}

        # Hot reload callback management
        # Queue of events to process after reload
        self._lifecycle_event_queue: List[LifeCycleEvent] = []

        # Other registries that depend on this one
        self._registry_subscribers: List[HotReloadRegistry] = []
        # Direct consumers (factories, etc.)
        self._batch_event_subscribers: List[LifeCycleBatchCallback] = []

        self._dependency_module_lifecycle_events: Dict[str, LifeCycleEvent] = {}
        """Track errors during dependency module reloads and store them by registry_key"""

        self.logger = logging.getLogger(__name__)

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
        """List all classes registry_keys in this registry"""
        return list(self._classes.keys())

    def _register(
        self, registry_key: str, cls: Any, library_identity: Optional[LibraryIdentity] = None
    ) -> str | None:
        """
        Register a class with its name and optional metadata
        Args:
            registry_key (str): The haywire registry_key of the class to register
            cls (Any): The class to register
            library_identity (Optional[LibraryIdentity]):
                The library identity to associate with the class
        Returns:
            str: The haywire registry_key of the registered class
        """
        library_label = library_identity.label if library_identity is not None else "<unknown>"

        # Check if class_identity exists
        if not hasattr(cls, "class_identity"):
            raise ValueError(
                f"Library '{library_label}': Class {cls} does not "
                f"have a class_identity attribute. Cannot register. This is "
                f"likely due to a missing condition in the implementation of "
                f"the registry's class filter method."
            )

        # Check for duplicates
        if self.has(registry_key):
            raise ValueError(
                f"Library '{library_label}': "
                f"Attempt to register Node '{cls.class_identity.label}' "
                f"under an existing registry_key '{registry_key}'. "
                f"This is not allowed. Indication of double use of a node "
                f"registry_id or node class name."
            )

        # Register the class
        self._classes[registry_key] = cls

        self._regkey_to_class_name[registry_key] = cls.__name__

        # Track module to class mapping
        module_name = cls.__module__
        if module_name not in self._module_to_registry_keys:
            self._module_to_registry_keys[module_name] = []
        if registry_key not in self._module_to_registry_keys[module_name]:
            self._module_to_registry_keys[module_name].append(registry_key)

        return registry_key

    def _unregister(self, registry_key: str) -> type[Any] | None:
        """
        Remove a class from the registry
        Args:
            registry_key (str): The haywire registry_key of the class to unregister
        Returns:
            type[Any] | None: The unregistered class, or None if not found
        """

        if registry_key in self._regkey_to_class_name:
            del self._regkey_to_class_name[registry_key]

        # Remove from registry
        delete_cls = self._classes.get(registry_key)
        if registry_key in self._classes:
            # Clean up module to class mapping
            module_name = delete_cls.__module__
            if module_name in self._module_to_registry_keys:
                if registry_key in self._module_to_registry_keys[module_name]:
                    self._module_to_registry_keys[module_name].remove(registry_key)
                    if not self._module_to_registry_keys[module_name]:
                        del self._module_to_registry_keys[module_name]
            # Finally delete the class
            del self._classes[registry_key]
        return delete_cls

    # ============================================================================
    # Folder-Aware Registry (File System Integration)
    # ============================================================================

    def add_folder(
        self,
        folder_path: str,
        library_identity: LibraryIdentity,
        exclude_patterns: Optional[list[str]] = None,
    ):
        """
        Initial scan of the folder for classes matching the registry's class filter
        and add them to this registry.

        This method is called by the library when it is enabled.

        Args:
            folder_path (str): Path to the folder to scan
            exclude_patterns (Optional[list[str]]): List of filename patterns to exclude
        """
        if folder_path in self._folder_to_library:
            logger.warning(
                f"Library '{library_identity.label}': Folder "
                f"'{folder_path[len(library_identity.folder_path) :]}' is already registered "
                f"in registry '{self.__class__.__name__}'. Skipping."
            )
            return

        self._folder_to_library[folder_path] = library_identity

        rel_path = folder_path[len(library_identity.folder_path) :]
        logger.info(
            f"Library '{library_identity.label}': START Scanning folder "
            f"'{rel_path}' for files to register classes..."
        )

        file_paths = self.folder_scan_for_pyfiles(folder_path, exclude_patterns)

        module_name = "Unknown"

        for file_path in file_paths:
            try:
                if self._validate_python_file(file_path):
                    resolved = self.resolve_module_name(
                        file_path, library_identity.folder_path, library_identity.module_name
                    )
                    if resolved is None:
                        logger.warning(
                            f"Library '{library_identity.label}': could not resolve module name "
                            f"for {file_path}. Skipping."
                        )
                        continue
                    module_name = resolved
                    self._on_creation(module_name, library_identity)

            except Exception as e:
                try:
                    HaywireException.from_exception(
                        exception=e,
                        operation="Registry folder import",
                        message=(
                            f"Failed while importing folder '{file_path}' in "
                            f"library '{library_identity.label}'"
                        ),
                    ).enrich(module_name=module_name, library_identity=library_identity).log()
                except Exception:
                    logger.error(
                        f"Library '{library_identity.label}': Failed notifying registry : {e}", exc_info=True
                    )

        self._notify_batch_event_subscribers()

        logger.info(
            f"Library '{library_identity.label}': ... Scanning folder -> DONE. "
            f"{len(file_paths)} files processed."
        )

    def remove_folder(
        self,
        folder_path: str,
        library_identity: LibraryIdentity,
        exclude_patterns: Optional[list[str]] = None,
    ):
        """
        Remove all classes associated with a library_identity from this registry.
        This method is called by the library when it is disabled.

        Args:
            folder_path (str): Path to the folder to remove
            exclude_patterns (Optional[list[str]]): List of filename patterns to exclude
        """
        del self._folder_to_library[folder_path]

        file_paths = self.folder_scan_for_pyfiles(folder_path, exclude_patterns)

        module_name = "Unknown"

        for file_path in file_paths:
            try:
                resolved = self.resolve_module_name(
                    file_path, library_identity.folder_path, library_identity.module_name
                )
                if resolved is None:
                    logger.warning(
                        f"Library '{library_identity.label}': could not resolve module name "
                        f"for {file_path}. Skipping."
                    )
                    continue
                module_name = resolved
                self._on_delete(module_name, library_identity)

            except Exception as e:
                try:
                    rel_path = folder_path[len(library_identity.folder_path) :]
                    HaywireException.from_exception(
                        exception=e,
                        operation="Registry folder import",
                        message=(
                            f"Failed while importing folder '...{rel_path}' in "
                            f"library '{library_identity.label}'"
                        ),
                    ).enrich(module_name=module_name, library_identity=library_identity).log(self.logger)
                except Exception:
                    logger.error(f"Library '{library_identity.label}': Failed notifying registry : {e}")

        self._notify_batch_event_subscribers()

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
        module_name = None

        try:
            # Skip validation for deleted files
            logger.info(
                f"Library '{event.library_identity.label}': "
                f"Registry '{self.__class__.__name__}': "
                f"DETECTED Hot Reloading event: file-'{event.event_type.value}' "
                f"on file: {event.file_path[len(event.library_identity.folder_path) :]}. "
                f"INITIATING ..."
            )

            # Resolve module name..
            file_path = Path(event.file_path)
            resolved = self.resolve_module_name(
                file_path, event.library_identity.folder_path, event.library_identity.module_name
            )
            if resolved is None:
                self.logger.error(
                    f"Library '{event.library_identity.label}': could not resolve module name "
                    f"for {file_path}. Skipping Hot Reloading."
                )
                return None
            module_name = resolved

            # ... before validating the file
            if event.event_type != FileEventType.DELETED:  # no need to validate deleted files
                if not self._validate_python_file(event.file_path):
                    self.logger.error(
                        f"Library '{event.library_identity.label}': "
                        f"Invalid Python file: {event.file_path}. Skipping Hot Reloading."
                    )
                    return None

            if event.dependency_event or event.event_type == FileEventType.MODIFIED:
                if module_name in sys.modules:
                    self._on_change(module_name, event.library_identity, event)
                else:
                    # covering an edge case where a module is modified but
                    # not yet loaded
                    self.logger.info(
                        f"Library '{event.library_identity.label}': Module "
                        f"'{module_name}' not found in sys.modules. Creating "
                        f"new module."
                    )
                    self._on_creation(module_name, event.library_identity)
            elif not event.dependency_event:
                if event.event_type == FileEventType.CREATED:
                    self._on_creation(module_name, event.library_identity)
                if event.event_type == FileEventType.DELETED:
                    self._on_delete(module_name, event.library_identity)

            self.logger.info(f"Library '{event.library_identity.label}': ...Hot Reloading -> DONE.")

            # Event now contains all reloaded_modules
            # Flag as dependency event if applicable to inform subscribers about its nature
            event.dependency_event = True
            # Notify registry subscribers after successful reload
            self._notify_registry_subscribers(event)

            self._notify_batch_event_subscribers()

        except Exception as e:
            self._lifecycle_event_queue.clear()  # Clear any pending events
            if module_name:
                if event.event_type == FileEventType.MODIFIED:
                    # Reload failed during modification
                    for key in self._module_to_registry_keys.get(module_name, []):
                        error = HaywireException.from_exception(
                            exception=e,
                            operation="Registry Hotreload File Module Reload",
                            message=(
                                f"Failed reloading module '{module_name}' in "
                                f"library '{event.library_identity.label}'"
                            ),
                        ).enrich(
                            registry_key=key,
                            module_name=module_name,
                            library_identity=event.library_identity,
                        )
                        lc_event = LifeCycleEvent(
                            registry_key=key,
                            event_type=LifeCycleEventType.CLASS_RELOAD_FAILED,
                            affected_class=self.get(key),
                            library_identity=event.library_identity,
                            module_name=module_name,
                            error=error,
                        )
                        # one might be tempted to unregister the class here,
                        # but we want to keep the broken class registered so that
                        # we can report its error state to consumers
                        self._queue_lifecycle_event(lc_event)
                    self._notify_batch_event_subscribers()
                elif event.dependency_event and len(self._dependency_module_lifecycle_events) > 0:
                    # Notify subscribers about dependency reload failure
                    for lc_event in self._dependency_module_lifecycle_events.values():
                        self._queue_lifecycle_event(lc_event)
                    self._notify_batch_event_subscribers()
                    self._dependency_module_lifecycle_events.clear()
            try:
                HaywireException.from_exception(
                    exception=e,
                    operation="Registry Hotreload Callback",
                    message=(
                        f"Failed notifying about file {event.event_type.value} "
                        f"in library '{event.library_identity.label}'"
                    ),
                ).enrich(
                    module_name=locals().get("module_name", "unknown"),
                    library_identity=event.library_identity,
                ).log(self.logger)
            except Exception as logging_error:
                self.logger.error(
                    f"Library '{event.library_identity.label}': "
                    f"Failed notifying registry on file:{event.file_path}' :"
                    f" {logging_error}"
                )

            self.logger.error(
                f"Library '{event.library_identity.label}': "
                f"...Hot Reloading on file on file: {event.file_path} -> FAILED."
            )

    def _on_creation(self, module_name: str, library_identity: LibraryIdentity):
        """called when a new module is created / loaded
        Args:
            module (str): The module name that has been created.
        Returns:
            list: List of relevant classes that are in this module
        """
        if module_name is None:
            return  # Skip processing if validation failed

        # force_reload=False: if the module is already in sys.modules
        # (because some earlier import path loaded it), keep that class
        # object — re-importing would produce a fresh class and leave
        # any pre-existing references stale. Hot-reload of changed
        # files goes through _reload_managed_module, not here.
        added_classes, _ = self.module_scan_for_classes(module_name, library_identity, self._class_filter)
        if added_classes:
            # Get tracking scopes from library dependencies
            scope_prefixes = self._get_tracking_scopes(library_identity)

            # This module contains managed classes - track it with scope prefixes
            self._dependency_graph.add_managed_module(module_name, scope_prefixes)

            for cls in added_classes:
                new_key = self._register_class(cls, library_identity)
                # Emit event for added class
                if new_key:
                    event = LifeCycleEvent(
                        registry_key=new_key,
                        event_type=LifeCycleEventType.CLASS_ADDED,
                        affected_class=cls,
                        library_identity=library_identity,
                        module_name=module_name,
                    )
                    self._queue_lifecycle_event(event)

    def _on_change(
        self, module_name: str, library_identity: LibraryIdentity, event: Optional[FileChangeEvent] = None
    ):
        """
        re-registering existing classes within the module
        and returning the classes that need to be
        additionally registered / unregistered
        Args:
            module_name (str): The module name that has changed.
            event (Optional[FileChangeEvent]): The file change event
                (used to track reloaded modules)
        Returns:
            [list,list]: [(List of classes to be registered),
                         (List of haywire class names to be unregistered)]
        """
        if module_name is None:
            return  # Skip processing if validation failed

        self.logger.info(
            f"Library '{library_identity.label}': Analyzing dependencies for "
            f"changed module '{module_name}'..."
        )

        # Get modules to exclude (already reloaded by upstream registries)
        exclude_modules = event.reloaded_modules if event else set()

        # Get reload plan from dependency graph, excluding already-reloaded modules
        reload_plan = self._dependency_graph.get_reload_plan(module_name, exclude_modules)

        self.logger.info(
            f"Library '{library_identity.label}': Reload plan: "
            f"{len(reload_plan.non_managed_modules)} helpers, "
            f"{len(reload_plan.managed_modules)} managed modules to reload."
        )

        # reset dependency errors for this reload
        self._dependency_module_lifecycle_events.clear()

        # Step 1: Reload non-managed helper modules first
        for helper_module in reload_plan.non_managed_modules:
            if helper_module in sys.modules:
                self._reload_unmanaged_module(helper_module, library_identity, event)

        # If any dependency module reloads failed, abort managed module reloads
        if len(self._dependency_module_lifecycle_events) > 0:
            raise Exception(
                f"Library '{library_identity.label}': "
                f"Dependency module reload errors detected. "
                f"Aborting managed module reload."
            )

        # Step 2: Reload managed modules using registry's special handling
        for managed_module in reload_plan.managed_modules:
            self.logger.info(
                f"Library '{library_identity.label}': Reloading managed module '{managed_module}'..."
            )
            self._reload_managed_module(managed_module, library_identity)
            # Track that we reloaded this module
            if event:
                event.reloaded_modules.add(managed_module)

    def _reload_unmanaged_module(
        self, module_name: str, library_identity: LibraryIdentity, event: Optional[FileChangeEvent] = None
    ):
        """
        Reload a single unmanaged module without registry-specific handling.
        Catches ModuleNotFoundError to log dependency errors.
        Called by the _on_change method.
        """
        try:
            self.logger.info(
                f"Library '{library_identity.label}': Reloading helper module '{module_name}'..."
            )
            importlib.reload(sys.modules[module_name])
            # Track that we reloaded this module
            if event:
                event.reloaded_modules.add(module_name)
        except Exception as e:
            if event is None:
                # No source event to associate the dependency error with;
                # the cascade-tracking dict is keyed by event context.
                self.logger.warning(
                    f"Library '{library_identity.label}': failed reloading dependency "
                    f"module '{module_name}' but no source event provided to track."
                )
                return
            managed_modules = self._dependency_graph._find_managed_dependents(module_name)
            for managed_module in managed_modules:
                error = (
                    HaywireException.create(
                        category=e.__class__.__name__,
                        operation="Registry Unmanaged Module Hot-Reload",
                        message=(
                            f"Failed reloading dependency module "
                            f"'{module_name}' required by managed module "
                            f"'{managed_module}'. {str(e)}"
                        ),
                    )
                    .enrich(
                        module_name=managed_module,
                        library_identity=library_identity,
                        suggestions=[
                            "Check that the dependency module exists and is correctly installed.",
                            "Ensure that the dependency module is accessible from the Python environment.",
                        ],
                    )
                    .log(self.logger)
                )
                reg_keys = self._module_to_registry_keys.get(managed_module, [])
                for key in reg_keys:
                    lc_event = LifeCycleEvent(
                        registry_key=key,
                        event_type=LifeCycleEventType.CLASS_RELOAD_FAILED,
                        affected_class=self.get(key),
                        library_identity=event.library_identity,
                        module_name=module_name,
                        error=error,
                    )
                    self._dependency_module_lifecycle_events[key] = lc_event

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
            classes_to_add, module = self.module_scan_for_classes(
                module_name,
                library_identity=library_identity,
                class_filter=self._class_filter,
                force_reload=True,
            )
            class_names_to_remove = []
            # Simple container for old/new class pairs

            classes_to_reload: List[Tuple[str, Type[Any]]] = []

            # Get registered classes from this module that need to be updated
            class_reg_keys_to_update = self._module_to_registry_keys.get(module_name, [])
            if class_reg_keys_to_update:
                # Store old class info for re-registration
                # module class name -> haywire class registry_key
                mod_to_class_name_mapping: Dict[str, str] = {}
                for mod_class_reg_key in class_reg_keys_to_update:
                    mod_to_class_name_mapping[self._regkey_to_class_name[mod_class_reg_key]] = (
                        mod_class_reg_key
                    )
                    # check if the registered old class name matches a class
                    # name in the new module
                    class_to_remove = next(
                        (
                            cls
                            for cls in classes_to_add
                            if cls.__name__ == self._regkey_to_class_name[mod_class_reg_key]
                        ),
                        None,
                    )
                    if class_to_remove:
                        # Remove the class from the list to avoid re-registering it
                        classes_to_add.remove(class_to_remove)

                # Re-register classes from reloaded module
                for mod_class_reg_key in mod_to_class_name_mapping:
                    if hasattr(module, mod_class_reg_key):
                        # to update a class, we need to unregister the old one
                        # and register the new one
                        new_class: Type[Any] = getattr(module, mod_class_reg_key)
                        old_class_name = mod_to_class_name_mapping[mod_class_reg_key]
                        classes_to_reload.append((old_class_name, new_class))
                    else:
                        class_names_to_remove.append(mod_to_class_name_mapping[mod_class_reg_key])

            cls_names_to_remove = class_names_to_remove.copy()

            # If we have an exception during re-registration, but we got so far
            # we need to rollback AND re-register all classes from the snapshot
            if snapshot:
                snapshot["needs_reregistring"] = True

            if classes_to_reload:
                for old_cls_name, new_cls in classes_to_reload:
                    self._unregister_class(old_cls_name)
                    new_key = self._register_class(new_cls, library_identity)
                    logger.info(
                        f"Library '{library_identity.label}': "
                        f"...Re-loaded and re-registered "
                        f"{new_cls.class_identity.registry_key} from {module_name}"
                    )
                    # Notify customer callbacks about reloaded class
                    if new_key:
                        event = LifeCycleEvent(
                            registry_key=new_key,
                            event_type=LifeCycleEventType.CLASS_RELOADED,
                            affected_class=new_cls,
                            library_identity=library_identity,
                            module_name=module_name,
                        )
                        self._queue_lifecycle_event(event)
            if cls_names_to_remove:
                for cls_name in cls_names_to_remove:
                    removed_cls = self._unregister_class(cls_name)
                    # Notify customer callbacks about removed class
                    if removed_cls:
                        event = LifeCycleEvent(
                            registry_key=cls_name,
                            event_type=LifeCycleEventType.CLASS_REMOVED,
                            affected_class=None,
                            library_identity=library_identity,
                            module_name=module_name,
                        )
                        self._queue_lifecycle_event(event)
            if classes_to_add:
                for cls in classes_to_add:
                    new_key = self._register_class(cls, library_identity)
                    # Notify customer callbacks about added class
                    if new_key:
                        event = LifeCycleEvent(
                            registry_key=new_key,
                            event_type=LifeCycleEventType.CLASS_ADDED,
                            affected_class=cls,
                            library_identity=library_identity,
                            module_name=module_name,
                        )
                        self._queue_lifecycle_event(event)

        except Exception as e:
            logger.error(f"Library '{library_identity.label}': Reload failed for '{module_name}': {e}")
            if snapshot is not None:
                self._rollback_snapshot(module_name, snapshot, library_identity)
            raise

    def _on_delete(self, module_name: str, library_identity: LibraryIdentity):
        """Called when a module is deleted or unloaded.
        Args:
            module (str): The module name that has been deleted.
        """
        if module_name is None:
            return  # Skip processing if validation failed (shouldn't happen for DELETE events)

        class_reg_keys_to_delete = self._module_to_registry_keys.get(module_name, [])
        removed_classes = class_reg_keys_to_delete.copy()

        if removed_classes:
            for cls_name in removed_classes:
                removed_cls = self._unregister_class(cls_name)
                # Emit event for removed class
                if removed_cls:
                    event = LifeCycleEvent(
                        registry_key=cls_name,
                        event_type=LifeCycleEventType.CLASS_REMOVED,
                        affected_class=removed_cls,
                        library_identity=library_identity,
                        module_name=module_name,
                    )
                    self._queue_lifecycle_event(event)

        # Remove from dependency graph if no more managed classes
        if not self._module_to_registry_keys.get(module_name):
            self._dependency_graph.remove_managed_module(module_name)

    # ============================================================================
    # Snapshot Registry (Rollback Support)
    # ============================================================================

    def _create_rollback_snapshot(self, module_name: str) -> Optional[Dict[str, Any]]:
        """Create snapshot of module state for rollback"""
        if module_name not in sys.modules:
            return None

        module = sys.modules[module_name]
        snapshot: Dict[str, Any] = {
            "module": module,
            "needs_reregistring": False,
            "registered_classes": {},
        }

        # Snapshot registered classes from this module
        for hw_name in self._module_to_registry_keys.get(module_name, []):
            snapshot["registered_classes"][hw_name] = {
                "class": self._classes.get(hw_name),
                "class_name": self._regkey_to_class_name.get(hw_name),
            }

        return snapshot

    def _rollback_snapshot(
        self, module_name: str, snapshot: Dict[str, Any], library_identity: LibraryIdentity
    ):
        """Restore module from snapshot after failed reload"""
        if snapshot:
            # Restore module in sys.modules
            sys.modules[module_name] = snapshot["module"]

            if snapshot["needs_reregistring"]:
                # Re-register classes from snapshot
                for hw_name, class_info in snapshot["registered_classes"].items():
                    self._unregister_class(class_info["class"].class_identity.registry_key)
                    self._register_class(class_info["class"], library_identity)

            self.logger.info(f"Library '{library_identity.label}': Rollback complete for '{module_name}'")

    # ============================================================================
    # Dependency Scope Management
    # ============================================================================

    def _get_tracking_scopes(self, library_identity: LibraryIdentity) -> List[str]:
        """
        Get all scope prefixes this module should track dependencies for.

        Returns scopes based on:
        1. Own library module name (always tracked)
        2. Declared dependencies from LibraryIdentity.dependencies
        3. Core framework (always tracked, unless we ARE core)

        Args:
            library_identity: The library identity containing dependency information

        Returns:
            List of module prefixes to track (e.g., ['mylib.', 'otherlib.', 'core.'])
        """
        scopes = []

        # Always track own library
        scopes.append(library_identity.module_name + ".")

        # Add declared library dependencies
        if library_identity.dependencies:
            for dep_lib_id in library_identity.dependencies:
                # Dependencies are library IDs (e.g., 'haywire.widgets')
                # Convert to module prefix by adding dot
                scopes.append(dep_lib_id + ".")

        self.logger.debug(f"Library '{library_identity.label}': Tracking scopes: {scopes}")

        return scopes

    # ============================================================================
    # Hot Reload Callback Management
    # ============================================================================

    def add_batch_event_subscriber(self, callback: LifeCycleBatchCallback) -> None:
        """
        Register a customer callback to be notified of hot reload events.

        Customer callbacks are invoked immediately after a class is reloaded,
        added, or removed. They receive a LifeCycleEvent batch with complete context.

        Args:
            callback: Function to call on life cycle events with signature:
                     (event: List[LifeCycleEvent]) -> None
        """
        if callback not in self._batch_event_subscribers:
            self._batch_event_subscribers.append(callback)
            self.logger.debug(f"Registered customer callback: {callback.__name__}")

    def remove_batch_event_subscriber(self, callback: LifeCycleBatchCallback) -> None:
        """
        Unregister a customer callback.

        Args:
            callback: The callback to remove
        """
        if callback in self._batch_event_subscribers:
            self._batch_event_subscribers.remove(callback)
            self.logger.debug(f"Removed customer callback: {callback.__name__}")

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
            self.logger.debug(
                f"{self.__class__.__name__}: Registered registry subscriber: {registry.__class__.__name__}"
            )

    def remove_registry_subscriber(self, registry: HotReloadRegistry) -> None:
        """
        Unregister a registry subscriber.

        Args:
            registry: The registry to unsubscribe
        """
        if registry in self._registry_subscribers:
            self._registry_subscribers.remove(registry)
            self.logger.debug(f"Removed registry subscriber: {registry.__class__.__name__}")

    def _queue_lifecycle_event(self, event: LifeCycleEvent) -> None:
        """
        Queues a hot reload event.

        This method is called internally during hot reload operations.
        Errors in individual callbacks are logged but don't stop generation of events.

        Args:
            event: The hot reload event with complete context
        """
        self._regkey_to_last_lifecycle_event[event.registry_key] = event

        self._lifecycle_event_queue.append(event)

    def _notify_batch_event_subscribers(self) -> None:
        """
        Batch notify all customer callbacks about hot reload events.

        This method is called internally during hot reload operations.

        Callbacks receive the complete event information.:

        """

        for callback in self._batch_event_subscribers[:]:
            callback(self._lifecycle_event_queue)

        self._lifecycle_event_queue.clear()

    def _notify_registry_subscribers(self, event: FileChangeEvent) -> None:
        """
        Notify all registry subscribers about a hot reload event.

        This method is called after customer callbacks have been notified.
        Registry subscribers receive the complete event information and can
        perform their own dependency analysis and reloading.

        Args:
            event: The file change event that triggered the reload
        """
        for registry in self._registry_subscribers[:]:
            try:
                registry.event_dispatcher(event)
            except Exception as e:
                self.logger.error(
                    f"Registry subscriber '{registry.__class__.__name__}' "
                    f"callback failed for {event.file_path}: {e}",
                    exc_info=True,
                )
