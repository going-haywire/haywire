import os
import sys
import importlib
import traceback
from types import ModuleType
from typing import Any, Dict, Optional, Type
import logging

from ..library import BaseLibrary
from ..utils import format_external_exception

from ..library_identity import LibraryIdentity
from ..class_registry import BaseClassRegistry

logger = logging.getLogger(__name__)

class LibraryDiscoveryError(Exception):
    """Base exception for library discovery issues"""
    pass

class LibraryLoadError(LibraryDiscoveryError):
    """Library failed to load properly"""
    pass

class LibraryRegistry:
    """Registry for managing loaded libraries"""
    
    def __init__(self):
        # Registry functionality moved from BaseRegistry
        self._libraries: Dict[str, BaseLibrary] = {} # registry_id -> library_instance
        self._class_registries: Dict[Type[BaseClassRegistry], BaseClassRegistry] = {} # registry_cls -> registry instance
        
        # LibraryRegistry specific attributes
        self.discovered_libraries: Dict[str, Dict[str, Any]] = {}
        self._library_root_paths: list[str] = [] # Paths to search for libraries
        self._load_order: list[str] = []
        self.enforce_file_watching = False
        self.debounce_delay = 0.5

    def _register(self, library_instance: Any):
        """Register a library instance with its path"""
        library_registry_id = library_instance.identity.id

        self._libraries[library_registry_id] = library_instance

        if library_registry_id not in self._load_order:
            self._load_order.append(library_registry_id)

    def _unregister(self, registry_id: str) -> BaseLibrary | None:
        """Remove a library from the registry"""
        delete_library = self._libraries.get(registry_id)
        if registry_id in self._libraries:
            del self._libraries[registry_id]
        if registry_id in self._load_order:
            self._load_order.remove(registry_id)
        return delete_library

    def list_names(self) -> list[str]:
        """List all registered library names"""
        return list(self._libraries.keys())

    def add_class_registry(self, cls: Type[BaseClassRegistry], instance: BaseClassRegistry):
        """
        Add a registry instance for a given registry class
        This allows to dynamically add registries that libraries can use

        Args:
            cls: The class of the registry
            instance: The instance of the registry
        """
        self._class_registries[cls] = instance
    
    def add_library_root_path(self, path: str):
        """
        Add a path to search for libraries
        Each library root path is scanned for subdirectories containing a library structure.

        Args:
            path: The root path to add
        """
        if path not in self._library_root_paths:
            self._library_root_paths.append(path)

    def enable_file_watching(self, debounce_delay: float = 0.5, force: bool = False):
        """
        Enable file watching for library directories
        This overrides library settings to enforce file watching.

        Args:
            debounce_delay: Delay in seconds to debounce file change events
            force: Force enable even if library settings disable it
        """
        self.debounce_delay = debounce_delay
        self.enforce_file_watching = force


    def enable_all_libraries(self):
        """Enable file watching for all loaded libraries"""
        for library in self._libraries.values():
            library.enable()
    
    def enable_library(self, library_registry_id: str) -> bool:
        """Enable a specific library"""
        library = self._libraries.get(library_registry_id)
        if library:
            library.enable()
            logger.info(f"Library '{library.identity.label}': Enabled")
            return True
        return False
    
    def disable_library(self, library_registry_id: str) -> bool:
        """Disable a specific library"""
        library = self._libraries.get(library_registry_id)
        if library:
            library.disable()
            logger.info(f"Library '{library.identity.label}': Disabled")
            return True
        return False
    
    def is_library_enabled(self, library_registry_id: str) -> bool:
        """Check if a library is enabled"""
        library = self._libraries.get(library_registry_id)
        return library.enabled if library else False

    def scan_for_libraries(self):
        """
        Discover and load all libraries from the specified paths
        Each library root path is scanned for subdirectories containing a library structure.
        This method instantiates each library and lets it register its components.

        This method can be called multiple times to discover 
        new libraries added or removed at runtime.
        """

        # First discover all library lib folders
        discovered_lib_folders = {}
        for search_path in self._library_root_paths:
            logger.info(
                f"Scanning for libraries in: {search_path}")
            discovered_lib_folders.update(self._scan_directory(search_path))

        instantiated_libraries: Dict[str, BaseLibrary] = {}

        # instantiate new libraries with its metadata
        for library_folder_name, library_path in discovered_lib_folders.items():
            if not self._has_library_with_path(library_path):
                try:
                    library_cls = self._load_library_class(library_folder_name, library_path)
                    library_instance = library_cls(library_path, self.enforce_file_watching, self.debounce_delay)

                    # store them in the metadata name (and not the folder)
                    instantiated_libraries[library_instance.identity.id] = library_instance

                except Exception as e:
                    logger.error(
                        f"While attempting to load library '{library_folder_name}': "
                        f"\n\n {format_external_exception()}\n")

        # Load each library
        for library_id, library_instance in instantiated_libraries.items():
            try:                
                if library_instance:
                    # Add registries to the library
                    for reg_cls, ref_i in self._class_registries.items():
                        library_instance.add_registry(reg_cls, ref_i)

                    # Register the library
                    self._register(library_instance)
                    
                    # Add to the loaded libraries list
                    logger.info(
                        f"Successfully loaded library: '{library_instance.identity.label}' "
                        f"- deps: {library_instance.identity.dependencies}")

            except Exception as e:
                logger.error(
                    f"Failed to load library '{library_instance.identity.label}': "
                    f"{e} \n\n {format_external_exception()}\n")

        # check for removed libraries
        current_library_paths = {lib.file_path for lib in self._libraries.values()}
        for library_id, library_instance in list(self._libraries.items()):
            if library_instance.file_path not in discovered_lib_folders.values():
                logger.info(
                    f"Library '{library_instance.identity.label}': "
                    f"is being removed and unregistered.")
                
                # Unregister the library
                library_instance.disable()
                self._unregister(library_id)


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
                logger.error(
                    f"Library '{library_id}': "
                    f"Invalid library structure: missing __init__.py - file")
                
        except Exception as e:
            logger.error(f"Library '{library_id}': "
                         f"Error while checking library structure: {e}")

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
                    logger.error(
                        f"Library '{library_folder_name}': "
                        f"Has no a valid 'class_identity'. "
                        f"Check if @library decorator is applied to the class in '__init__.py' at '{library_path}'")
            else:
                logger.error(
                    f"Library with folder name '{library_folder_name}': "
                    f"Missing valid 'Library' class in '__init__.py' at '{library_path}'")
                
        except Exception as e:
            logger.error(
                f"Library {library_folder_name}: "
                f"Failed instantiating {e} \n {traceback.format_exc()}")
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
    
    def _has_library_with_path(self, path: str) -> bool:
        """Check if a library with the given path is already registered"""
        for lib in self._libraries.values():
            if lib.file_path == path:
                return True
        return False

    def get_load_order(self) -> list[str]:
        """Get the order in which libraries were loaded"""
        return self._load_order.copy()
    
    def get_library_identity(self, library_registry_id: str) -> LibraryIdentity | None:
        """Get metadata for a library"""
        library = self._libraries.get(library_registry_id)
        return library.class_identity if library else None

