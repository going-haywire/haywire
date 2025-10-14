import os
import sys
import importlib
import traceback
from types import ModuleType
from typing import Any, Dict, Optional
import logging

from haywire.core.inventory.library import BaseLibrary
from haywire.core.inventory.utils import format_external_exception

from ..library_identity import LibraryIdentity
from ..base import BaseRegistry, BaseClassRegistry

logger = logging.getLogger(__name__)

class LibraryDiscoveryError(Exception):
    """Base exception for library discovery issues"""
    pass


class LibraryStructureError(LibraryDiscoveryError):
    """Library doesn't follow required structure"""
    pass


class LibraryLoadError(LibraryDiscoveryError):
    """Library failed to load properly"""
    pass


class LibraryRegistry(BaseRegistry):
    """Registry for managing loaded libraries"""
    
    def __init__(self):
        super().__init__()
        self.discovered_libraries: Dict[str, Dict[str, Any]] = {}
        self._library_paths: list[str] = []
        self._load_order: list[str] = []
        self.registries = {}
        self.enforce_file_watching = False
        self.debounce_delay = 0.5

    def add_class_registry(self, cls, instance: BaseClassRegistry):
        """Add a registry instance for a given registry class"""
        self.registries[cls] = instance
    
    def add_library_path(self, path: str):
        """Add a path to search for libraries"""
        if path not in self._library_paths:
            self._library_paths.append(path)

    def enable_file_watching(self, debounce_delay: float = 0.5, force: bool = False):
        """Enable file watching for library directories"""
        self.debounce_delay = debounce_delay
        self.enforce_file_watching = force

    def load_libraries(self):
        # First discover all libraries

        discovered_lib_folders = {}
        for search_path in self._library_paths:
            logger.info(f"Scanning for libraries in: {search_path}")
            discovered_lib_folders.update(self._scan_directory(search_path))

        instantiated_libraries: Dict[str, BaseLibrary] = {}

        # instantiate each libraries with its metadata
        for library_folder_name, library_path in discovered_lib_folders.items():
            try:
                library_cls = self._load_library_class(library_folder_name, library_path)
                library_instance = library_cls(library_path, self.enforce_file_watching, self.debounce_delay)

                # store them in the metadata name (and not the folder)
                instantiated_libraries[library_instance.identity.id] = library_instance

            except Exception as e:
                logger.error(f"While attempting to load library '{library_folder_name}': \n\n {format_external_exception()}\n")

        # Load each library
        for library_id, library_instance in instantiated_libraries.items():
            try:                
                if library_instance:
                    # Add registries to the library
                    for reg_cls, ref_i in self.registries.items():
                        library_instance.add_registry(reg_cls, ref_i)

                    # Register the library
                    self._register_library(library_instance)
                    
                    # Let the library register its components
                    library_instance.register_components()
                    
                    # Add to the loaded libraries list
                    logger.info(f"Successfully loaded library: '{library_instance.identity.label}' - deps: {library_instance.identity.dependencies}")

            except Exception as e:
                logger.error(f"Failed to load library '{library_instance.identity.label}': {e} \n\n {format_external_exception()}\n")

    def _scan_directory(self, directory: str) -> Dict[str, str]:
        """Scan a directory for library subdirectories"""
        lib_folders = {}
        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isdir(item_path) and not item.startswith('.') and not item.startswith('__pycache__'):
                    if self._check_library_structure(item, item_path):
                        lib_folders[item] = item_path
                        logger.info(f"Valid library found: '{item}' at {item_path}")
        except OSError as e:
            logger.error(f"Scanning library directory '{directory}': {e}")
        
        return lib_folders

    def _check_library_structure(self, library_id: str, library_path: str) -> bool:
        """Check if a directory follows the required library structure"""
        try:
            # Check for __init__.py
            init_file = os.path.join(library_path, '__init__.py')
            is_valid = os.path.exists(init_file)
            if is_valid:
                return True
            else:
                logger.warning(f"Invalid library structure: library '{library_id}' is missing __init__.py - file")
        except Exception as e:
            logger.error(f"Checking library structure for '{library_id}': {e}")

        return False    

    def _load_library_class(self, library_folder_name: str, library_path: str) -> type[BaseLibrary]:
        """Load a library class from its path"""       
        try:
            # Use the existing metadata loading method to get both module and metadata
            module = self._load_module_and_metadata(library_folder_name, library_path)
            if module and hasattr(module, 'Library'):
                if hasattr(module.Library, 'class_identity'):
                    return module.Library
                else:
                    logger.error(f"Library '{library_folder_name}' does not have a valid 'class_identity'. Check if @library decorator is applied to the class in '__init__.py' at '{library_path}'")
            else:
                logger.error(f"Library '{library_folder_name}' does not have a valid 'Library' class in '__init__.py' at '{library_path}'")
        except Exception as e:
            logger.error(f"Failed instantiating library {library_folder_name}: {e} \n {traceback.format_exc()}")
            raise LibraryLoadError(f"Failed instantiating library {library_folder_name}: {e}")

    def _load_module_and_metadata(self, library_id: str, library_path: str) -> Optional[ModuleType]:
        """Load module and metadata from a library's __init__.py. Always returns LibraryIdentity (with defaults if needed)."""
        module = None
        parent_dir_added = False
        
        # Determine the proper module path for import
        # Check if this is a core library (in src/haywire/libraries/)
        if 'src/haywire/libraries' in library_path:
            # For core libraries, use the haywire.libraries.X import path
            module_path = f"haywire.libraries.{library_id}"
        else:
            # For external libraries, add parent to sys.path and import directly
            parent_dir = os.path.dirname(library_path)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
                parent_dir_added = True
            module_path = library_id
        
        # Import the module using the proper path
        module = importlib.import_module(module_path)
        
        # Remove from sys.path if we added it
        if parent_dir_added and 'src/haywire/libraries' not in library_path:
            parent_dir = os.path.dirname(library_path)
            if parent_dir in sys.path:
                sys.path.remove(parent_dir)
        
        return module
    
    def _register_library(self, library_instance: Any):
        """Register a library instance with its path"""
        library_registry_id = library_instance.identity.id

        self._register(library_registry_id, library_instance)

        if library_registry_id not in self._load_order:
            self._load_order.append(library_registry_id)
    
    def get_load_order(self) -> list[str]:
        """Get the order in which libraries were loaded"""
        return self._load_order.copy()
    
    def get_library_identity(self, library_registry_id: str) -> LibraryIdentity | None:
        """Get metadata for a library"""
        library = self.get(library_registry_id)
        return library.class_identity if library else None

