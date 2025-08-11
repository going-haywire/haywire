"""
Registry implementations for widgets, adapters, and libraries
"""

from typing import Any, Optional

from ..base import BaseRegistry, LibraryMetadata

# Import core data types for widget fallback

class LibraryRegistry(BaseRegistry):
    """Registry for managing loaded libraries"""
    
    def __init__(self):
        super().__init__()
        self._library_paths: dict[str, str] = {}
        self._load_order: list[str] = []
    
    def register_library(self, library_instance: Any, library_path: str):
        """Register a library instance with its path"""
        library_name = library_instance.metadata.name

        self._register(library_name, library_instance)

        self._library_paths[library_name] = library_path
        if library_name not in self._load_order:
            self._load_order.append(library_name)
    
    def get_library_path(self, library_name: str) -> str | None:
        """Get the filesystem path for a library"""
        return self._library_paths.get(library_name)
    
    def get_load_order(self) -> list[str]:
        """Get the order in which libraries were loaded"""
        return self._load_order.copy()
    
    def get_library_metadata(self, library_name: str) -> LibraryMetadata | None:
        """Get metadata for a library"""
        library = self.get(library_name)
        return library.metadata if library else None

