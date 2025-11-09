from abc import ABC, abstractmethod
import logging
from pathlib import Path
from typing import Callable, Dict, List, Tuple, Type, TypeVar, Optional, Union
import inspect

from haywire.core.library.file_watcher import FileWatcher
from haywire.core.library.library_identity import LibraryIdentity
from haywire.core.library.class_registry import BaseClassRegistry, FileChangeEvent

# ============================================================================
#    Decorator
# ============================================================================

T = TypeVar('T')

def library(cls: Type[T] = None, /, **kwargs) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """
    Decorator to register a class as a Haywire library.
    
    Accepts any LibraryIdentity field as a keyword argument. Common arguments include:
    
    Args:
        label (str, required): Human-readable library name.
        version (str, optional): Semantic version string. Defaults to '1.0.0'.
        description (str, optional): Human-readable description of the library.
            Defaults to empty string.
        url (str, optional): Library's main URL. Defaults to empty string.
        help_url (str, optional): URL to documentation. Defaults to empty string.
        author (str, optional): Author name. Defaults to empty string.
        author_url (str, optional): Author's URL. Defaults to empty string.
        id (str, optional): Unique identifier for the library.
            Defaults to label if not provided.
        dependencies (list[str], optional): List of required haywire libraries.
            Defaults to empty list.
        file_watcher (bool, optional): Whether to enable file watching for this library.
            Defaults to False.
    
    Any other keyword arguments will be passed through to the LibraryIdentity constructor.
    See the LibraryIdentity dataclass for the complete list of available fields.

    Usage:
        # Minimal usage - only label is required
        @library(label="my.library")
        class Library(BaseLibrary): ...

        # Common customization
        @library(label="my.library", version="1.2.0", description="My custom library")
        class Library(BaseLibrary): ...

        # Full customization
        @library(
            label="advanced.library",
            version="2.0.0",
            description="Advanced library with many features",
            url="https://github.com/user/advanced-library",
            help_url="https://advanced-library.readthedocs.io",
            author="John Doe",
            author_url="https://johndoe.com",
            id="advanced_lib",
            dependencies=["haywire.core", "numpy"],
            file_watcher=True
        )
        class Library(BaseLibrary): ...

        # With file watching
        @library(label="dev.library", file_watcher=True, version="0.1.0")
        class Library(BaseLibrary): ...
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseLibrary):
            raise TypeError(f"@library can only be applied to BaseLibrary subclasses, got {inner_cls}")

        # Require label field
        if 'label' not in kwargs:
            raise ValueError("@library decorator requires 'label' argument")

        # Set defaults if not provided
        kwargs.setdefault('version', '1.0.0')
        kwargs.setdefault('id', kwargs['label'])
        
        # Auto-detect folder_path - use the directory where inner_cls is defined
        class_file = inspect.getfile(inner_cls)
        kwargs['folder_path'] = str(Path(class_file).parent)
        kwargs['module_name'] = inner_cls.__module__
        
        inner_cls.class_identity = LibraryIdentity(**kwargs)
        return inner_cls

    return decorator if cls is None else decorator(cls)

# ============================================================================
#    BASE CLASS
# ============================================================================

class BaseLibrary(ABC):
    """Abstract base class for all libraries"""

    def __init__(self, file_path: str, enforce_file_watching: bool = False, debounce_delay: float = 0.5):
        self.file_path = file_path
        self.registries = {}
        self.file_watcher: FileWatcher = FileWatcher()
        self.enforce_file_watching = enforce_file_watching
        self.debounce_delay = debounce_delay
        self._registry_folders: Dict[Type[BaseClassRegistry], Tuple[str, Optional[List[str]]]] = {} # registry_cls -> (folder_path, exclude_patterns)

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
        registry: Type[BaseClassRegistry] = self.get_registry(registry_cls)
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
        registry: Type[BaseClassRegistry] = self.get_registry(registry_cls)
        if not registry:
            raise ValueError(f"Registry {registry_cls} not found in library {self.identity.label}")

        registry.add_folder(folder_path, self.identity, exclude_patterns)

        if self.enforce_file_watching or self.identity.file_watcher:
            self.file_watcher.add_watch(folder_path, self.identity, registry, self.debounce_delay)
            logging.info(f"Library '{self.identity.label}': Started watching '{folder_path[len(self.identity.folder_path):]}' for hot reload events.")

    def _unregister_folder(self, folder_path: str, registry_cls: Type, exclude_patterns: Optional[List[str]] = None):
        """Inform the registry to remove classes from a folder and stop watching it if needed"""
        registry: Type[BaseClassRegistry] = self.get_registry(registry_cls)
        if not registry:
            raise ValueError(f"Registry {registry_cls} not found in library {self.identity.label}")

        registry.remove_folder(folder_path, self.identity, exclude_patterns)

        if self.enforce_file_watching or self.identity.file_watcher:
            self.file_watcher.remove_watch(folder_path)
            logging.info(f"Library '{self.identity.label}': Stopped watching '{folder_path[len(self.identity.folder_path):]}' for hot reload events.")

        