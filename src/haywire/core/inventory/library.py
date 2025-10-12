from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Type, TypeVar, Optional, Union

from haywire.core.inventory.library_identity import LibraryIdentity
from haywire.core.inventory.base import FileChangeEvent
from haywire.core.inventory.utils import resolve_module_name

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
        class MyLibrary(BaseLibrary): ...

        # Common customization
        @library(label="my.library", version="1.2.0", description="My custom library")
        class MyLibrary(BaseLibrary): ...

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
        class AdvancedLibrary(BaseLibrary): ...

        # With file watching
        @library(label="dev.library", file_watcher=True, version="0.1.0")
        class DevLibrary(BaseLibrary): ...
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
        
        inner_cls.library_metadata = LibraryIdentity(**kwargs)
        return inner_cls

    return decorator if cls is None else decorator(cls)

# ============================================================================
#    BASE CLASS
# ============================================================================

class BaseLibrary(ABC):
    """Abstract base class for all libraries"""

    def __init__(self, metadata: LibraryIdentity, file_path: str):
        self.metadata = metadata
        self.file_path = file_path
        self.registries = {}

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
            for registry in self.registries.values():
                if hasattr(registry, 'directory_name') and registry.directory_name == path_parts[1]:
                    registry.handle_module_change(module, event, self.metadata)
                    break

