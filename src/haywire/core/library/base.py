from abc import ABC, abstractmethod
import logging
from typing import Dict, List, Tuple, Type, TypeVar, Optional, Union

from haywire.core.library.file_watcher import FileWatcher
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import BaseRegistry, FileChangeEvent

# ============================================================================
#    BASE CLASS
# ============================================================================

class BaseLibrary(ABC):
    """
    Abstract base class for all libraries

    Usage:
    
    Libraries that extend this class **must** be named 'Library' 
    and be decorated with the @library decorator.
    """

    def __init__(self, file_path: str, enforce_file_watching: bool = False, debounce_delay: float = 0.5):
        self.file_path = file_path
        self.registries = {}
        self.file_watcher: FileWatcher = FileWatcher()
        self.enforce_file_watching = enforce_file_watching
        self.debounce_delay = debounce_delay
        self._registry_folders: Dict[Type[BaseRegistry], Tuple[str, Optional[List[str]]]] = {} # registry_cls -> (folder_path, exclude_patterns)

        self._enabled = False  # Library starts disabled by default

    @property
    def enabled(self) -> bool:
        """Check if the library is currently enabled"""
        return self._enabled

    def enable(self):
        """Enable the library and register its components"""
        if not self._enabled:
            self._enabled = True
            self.register_components()
            self._attach_to_registries()
            self.file_watcher.start()
            logging.info(f"Library '{self.identity.label}': Enabled and components registered")

    def disable(self):
        """Disable the library and remove its components from registries"""
        if self._enabled:
            self._enabled = False
            self._detach_from_registries()
            self.file_watcher.stop()
            logging.info(f"Library '{self.identity.label}': Disabled and components unregistered")
            
    @property
    def identity(self) -> LibraryIdentity:
        return self.__class__.class_identity

    def add_registry(self, cls, instance):
        """Add a registry instance for a given registry class"""
        self.registries[cls] = instance

    def get_registry(self, cls):
        """Get a registry instance by its class type"""
        return self.registries.get(cls)

    @abstractmethod
    def register_components(self):
        """
        Register this library's components with the global registries
        This method is called by the library registry when loading the library
        """
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate that this library is properly structured"""
        pass

    def add_folder_to_registry(self, folder_path: str, registry_cls: Type, exclude_patterns: Optional[List[str]] = None):
        """
        Scan a folder for classes matching the registry's class filter
        and add them to the specified registry.
        
        This method should only be called by the _init__ method within each library subfolder

        Args:
            folder: Relative folder path within the library
            registry_cls: The registry class to add discovered classes to
        """
        registry: Type[BaseRegistry] = self.get_registry(registry_cls)
        if not registry:
            raise ValueError(f"Registry {registry_cls} not found in library {self.identity.label}")

        self._registry_folders[registry_cls] = (folder_path, exclude_patterns)

    def _attach_to_registries(self):
        """Add ALL library classes to their registries"""
        for registry_cls, (folder_path, exclude_patterns) in self._registry_folders.items():
            self._register_folder(folder_path, registry_cls, exclude_patterns)

    def _detach_from_registries(self):
        """Remove ALL library classes from their registries"""
        for registry_cls, (folder_path, exclude_patterns) in self._registry_folders.items():
            self._unregister_folder(folder_path, registry_cls, exclude_patterns)

        self.file_watcher.stop()

    def _register_folder(self, folder_path: str, registry_cls: Type, exclude_patterns: Optional[List[str]] = None):
        """Inform the registry to add classes from a folder and start watching it if needed"""
        registry: Type[BaseRegistry] = self.get_registry(registry_cls)
        if not registry:
            raise ValueError(f"Registry {registry_cls} not found in library {self.identity.label}")

        registry.add_folder(folder_path, self.identity, exclude_patterns)

        if self.enforce_file_watching or self.identity.file_watcher:
            self.file_watcher.add_watch(folder_path, self.identity, registry, self.debounce_delay)
            logging.info(f"Library '{self.identity.label}': Started watching '{folder_path[len(self.identity.folder_path):]}' for hot reload events.")

    def _unregister_folder(self, folder_path: str, registry_cls: Type, exclude_patterns: Optional[List[str]] = None):
        """Inform the registry to remove classes from a folder and stop watching it if needed"""
        registry: Type[BaseRegistry] = self.get_registry(registry_cls)
        if not registry:
            raise ValueError(f"Registry {registry_cls} not found in library {self.identity.label}")

        registry.remove_folder(folder_path, self.identity, exclude_patterns)

        if self.enforce_file_watching or self.identity.file_watcher:
            self.file_watcher.remove_watch(folder_path)
            logging.info(f"Library '{self.identity.label}': Stopped watching '{folder_path[len(self.identity.folder_path):]}' for hot reload events.")

        