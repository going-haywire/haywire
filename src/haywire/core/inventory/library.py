from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Type, TypeVar, Optional, Union

from haywire.core.inventory.metadata import LibraryMetadata
from haywire.core.inventory.base import FileChangeEvent
from haywire.core.inventory.utils import resolve_module_name

# ============================================================================
#    Decorator
# ============================================================================

T = TypeVar('T')

def library(cls: Type[T] = None, /, *,
           label: str,
           version: str = '1.0.0',
           description: str = '',
           url: str = '',
           help_url: str = '',
           author: str = '',
           author_url: str = '',
           id: Optional[str] = None,
           dependencies: Optional[list[str]] = None,
           file_watcher: bool = False) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """
    Decorator to register a class as a Haywire library.

    Args:
        name: Unique library name (e.g., 'haywire.core')
        version: Semantic version string
        description: Human-readable description
        url: Library's main URL
        help_url: URL to documentation
        author: Author name
        author_url: Author's URL
        dependencies: List of required libraries
        file_watcher: Whether to enable file watching for this library

    Usage:
        @library(name="my.library", version="1.0.0", description="My library")
        class Library(BaseLibrary): ...
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseLibrary):
            raise TypeError(f"@library can only be applied to BaseLibrary subclasses, got {inner_cls}")

        # Create and attach metadata
        inner_cls.library_metadata = LibraryMetadata(
            label=label,
            version=version,
            description=description,
            url=url,
            help_url=help_url,
            author=author,
            author_url=author_url,
            dependencies=dependencies or [],
            file_watcher=file_watcher,
            id=id or label,
        )

        return inner_cls

    if cls is None:
        return decorator
    return decorator(cls)

# ============================================================================
#    BASE CLASS
# ============================================================================

class BaseLibrary(ABC):
    """Abstract base class for all libraries"""

    def __init__(self, metadata: LibraryMetadata, file_path: str):
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

