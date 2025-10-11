from haywire.core.inventory.base import FileChangeEvent, LibraryMetadata
from haywire.core.inventory.utils import resolve_module_name


from abc import ABC, abstractmethod
from pathlib import Path


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