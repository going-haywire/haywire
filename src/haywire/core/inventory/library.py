from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, List, Type, TypeVar, Optional, Union
import inspect

from haywire.core.inventory.file_watcher import FileWatcher
from haywire.core.inventory.library_identity import LibraryIdentity
from haywire.core.inventory.base import BaseClassRegistry, FileChangeEvent

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
        dependencies (list[str], optional): List of required libraries.
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
        """Register this library's components with the global registries"""
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate that this library is properly structured"""
        pass

    def add_folder_to_registry(self, folder_path: str, registry_cls: Type, exclude_patterns: Optional[List[str]] = None):
        """
        Scan a folder for classes matching the registry's class filter
        and add them to the specified registry.

        Args:
            folder: Relative folder path within the library
            registry_cls: The registry class to add discovered classes to
        """
        registry: Type[BaseClassRegistry] = self.get_registry(registry_cls)
        if not registry:
            raise ValueError(f"Registry {registry_cls} not found in library {self.identity.label}")

        registry.add_folder(folder_path, self.identity, exclude_patterns)

        if self.enforce_file_watching or self.identity.file_watcher:
            self.file_watcher.add_watch(folder_path, self.identity, registry, self.debounce_delay)
        

        