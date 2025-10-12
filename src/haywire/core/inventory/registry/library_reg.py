from typing import Any

from ..library_identity import LibraryIdentity

from ..base import BaseRegistry

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
    
    def get_library_metadata(self, library_registry_id: str) -> LibraryIdentity | None:
        """Get metadata for a library"""
        library = self.get(library_registry_id)
        return library.metadata if library else None

