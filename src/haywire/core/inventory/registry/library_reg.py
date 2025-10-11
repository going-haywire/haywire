from typing import Any, Optional, Type, TypeVar, Union, Callable

from ..base import BaseRegistry, LibraryMetadata

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
        from ..library import BaseLibrary
        
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

# Import core data types for widget fallback

class LibraryRegistry(BaseRegistry):
    """Registry for managing loaded libraries"""
    
    def __init__(self):
        super().__init__()
        self._library_paths: dict[str, str] = {}
        self._load_order: list[str] = []
    
    def register_library(self, library_instance: Any, library_path: str):
        """Register a library instance with its path"""
        library_registry_id = library_instance.metadata.id

        self._register(library_registry_id, library_instance, library_instance.metadata)

        self._library_paths[library_registry_id] = library_path
        if library_registry_id not in self._load_order:
            self._load_order.append(library_registry_id)
    
    def get_library_path(self, library_registry_id: str) -> str | None:
        """Get the filesystem path for a library"""
        return self._library_paths.get(library_registry_id)
    
    def get_load_order(self) -> list[str]:
        """Get the order in which libraries were loaded"""
        return self._load_order.copy()
    
    def get_library_metadata(self, library_registry_id: str) -> LibraryMetadata | None:
        """Get metadata for a library"""
        library = self.get(library_registry_id)
        return library.metadata if library else None

