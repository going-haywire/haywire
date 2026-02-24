import os
import sys
import importlib
import traceback
from types import ModuleType
from typing import Any, Dict, Optional, Type
from pathlib import Path
import logging

from .base import BaseLibrary
from .utils import format_external_exception
from .discovery import LibraryDiscovery, DiscoveredLibrary, InstallType
from .identity import LibraryIdentity
from ..registry.base import BaseRegistry

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
        self._libraries: Dict[str, BaseLibrary] = {}  # registry_id -> library_instance
        # registry_cls -> registry instance
        self._class_registries: Dict[Type[BaseRegistry], BaseRegistry] = {}
        
        # LibraryRegistry specific attributes
        self.discovered_libraries: Dict[str, Dict[str, Any]] = {}
        self._library_root_paths: list[str] = [] # Paths to search for libraries
        self._load_order: list[str] = []
        self.enforce_file_watching = False
        self.debounce_delay = 0.5
        
        # Track library sources to avoid duplicates
        self._library_sources: Dict[str, str] = {}  # library_id -> source path
        self._library_install_types: Dict[str, InstallType] = {}  # library_id -> install type
        self._library_distribution_names: Dict[str, str] = {}  # library_id -> pip package name
        
        # Loading configuration
        self.load_core_libraries = False  # Load core libraries from src/haywire/libraries
        self.load_pip_packages = True     # Load from pip installed packages
        self.core_libraries_path: Optional[str] = None  # Set during initialization

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

    def add_class_registry(self, cls: Type[BaseRegistry], instance: BaseRegistry):
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

    def remove_library(self, library_registry_id: str) -> bool:
        """Disable, unregister, and fully remove a library from all tracking dicts.

        After calling this, a subsequent scan_for_libraries() will rediscover
        and reimport the library from scratch, picking up any changes made to
        its source files (e.g. updated @library decorator values).
        """
        library = self._libraries.get(library_registry_id)
        if not library:
            return False
        library.disable()
        self._unregister(library_registry_id)
        self._library_sources.pop(library_registry_id, None)
        self._library_install_types.pop(library_registry_id, None)
        self._library_distribution_names.pop(library_registry_id, None)
        logger.info(f"Library '{library_registry_id}': Fully removed (ready for reload)")
        return True
    
    def is_library_enabled(self, library_registry_id: str) -> bool:
        """Check if a library is enabled"""
        library = self._libraries.get(library_registry_id)
        return library.enabled if library else False

    def scan_for_libraries(self):
        """
        Discover and load all libraries from multiple sources in priority order:
        1. Core libraries (hardcoded in src/haywire/libraries)
        2. Regular pip installs
        3. Editable pip installs (-e flag)
        4. Manual folder paths (avoiding duplicates)

        This method can be called multiple times to discover 
        new libraries added or removed at runtime.
        """
        logger.info("=" * 60)
        logger.info("Starting library discovery and loading process")
        logger.info("=" * 60)
        
        all_discovered: Dict[str, DiscoveredLibrary] = {}
        
        # Priority 1: Core libraries (if enabled)
        if self.load_core_libraries and self.core_libraries_path:
            logger.info("\n📦 Priority 1: Loading core libraries...")
            core_libs = self._discover_core_libraries()
            for lib in core_libs:
                all_discovered[lib.identity.id] = lib
                logger.info(f"  ✓ Found core library: {lib.identity.label} ({lib.identity.id})")
        
        # Priority 2 & 3: Pip installed packages (if enabled)
        if self.load_pip_packages:
            logger.info("\n📦 Priority 2 & 3: Loading pip installed packages...")
            pip_libs = LibraryDiscovery.discover_installed_libraries()
            
            for lib in pip_libs:
                # Skip if already loaded (e.g., core library already handled)
                if lib.identity.id in all_discovered:
                    logger.info(
                        f"  ⊘ Skipping {lib.identity.label} - already loaded as "
                        f"{all_discovered[lib.identity.id].install_type.value}"
                    )
                    continue
                
                all_discovered[lib.identity.id] = lib
                install_type_label = (
                    "regular install" 
                    if lib.install_type == InstallType.REGULAR 
                    else "editable install"
                )
                logger.info(
                    f"  ✓ Found {install_type_label}: "
                    f"{lib.identity.label} ({lib.identity.id})"
                )
        
        # Priority 4: Manual folder paths
        if self._library_root_paths:
            logger.info("\n📦 Priority 4: Scanning manual folder paths...")
            folder_libs = self._discover_folder_libraries()
            
            for lib in folder_libs:
                # Skip if already loaded from pip or core
                if lib.identity.id in all_discovered:
                    logger.info(
                        f"  ⊘ Skipping {lib.identity.label} - already loaded as "
                        f"{all_discovered[lib.identity.id].install_type.value}"
                    )
                    continue
                
                all_discovered[lib.identity.id] = lib
                logger.info(f"  ✓ Found folder library: {lib.identity.label} ({lib.identity.id})")
        
        # Instantiate and load all discovered libraries
        logger.info("\n🔨 Instantiating and loading libraries...")
        instantiated_libraries = self._instantiate_libraries(all_discovered)
        
        # Register all instantiated libraries
        logger.info("\n📝 Registering libraries...")
        for library_id, library_instance in instantiated_libraries.items():
            self._register_library_instance(library_instance)
        
        # Check for removed libraries
        self._cleanup_removed_libraries(all_discovered)
        
        logger.info("\n" + "=" * 60)
        logger.info(f"Library discovery complete: {len(self._libraries)} libraries loaded")
        logger.info("=" * 60)


    def _scan_directory(self, directory: str) -> Dict[str, str]:
        """Scan a directory for library subdirectories
        
        Returns:
            Dict mapping library_id -> actual module path containing __init__.py
        """
        lib_folders = {}
        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if (
                    os.path.isdir(item_path) 
                    and not item.startswith('.') 
                    and not item.startswith('__pycache__')
                ):
                    module_paths = self._check_library_structure(item, item_path)
                    for module_path in module_paths:
                        # Use the module folder name as the library_id
                        module_folder_name = os.path.basename(module_path)
                        lib_folders[module_folder_name] = module_path
                        logger.info(
                            f"Valid library found: '{module_folder_name}' "
                            f"at {module_path}"
                        )

        except OSError as e:
            logger.error(f"Scanning library directory '{directory}': {e}")
        
        return lib_folders

    def _check_library_structure(self, library_id: str, library_path: str) -> list[str]:
        """
        Check if a directory follows a valid library structure and return module paths.
        
        Two patterns:
        1. Flat structure: library_path/__init__.py (e.g., core library)
           → Returns [library_path]
        
        2. Package structure with pyproject.toml: library_path/pyproject.toml
           → Scans one level deep for folders with __init__.py
           → Returns list of all found module paths (can be multiple libraries in one package)
        
        Returns:
            List of paths to module directories containing __init__.py
        """
        module_paths = []
        
        try:
            # Check 1: Flat structure - __init__.py directly in library_path
            flat_init = os.path.join(library_path, '__init__.py')
            if os.path.exists(flat_init):
                return [library_path]
            
            # Check 2: Package structure - look for pyproject.toml
            pyproject_path = os.path.join(library_path, 'pyproject.toml')
            if os.path.exists(pyproject_path):
                # Scan one level deep for folders with __init__.py
                try:
                    for item in os.listdir(library_path):
                        item_path = os.path.join(library_path, item)
                        if (
                            os.path.isdir(item_path) 
                            and not item.startswith('.') 
                            and not item.startswith('__pycache__')
                        ):
                            init_path = os.path.join(item_path, '__init__.py')
                            if os.path.exists(init_path):
                                module_paths.append(item_path)
                
                except OSError as e:
                    logger.error(f"Error scanning package directory '{library_path}': {e}")
            
            if not module_paths:
                logger.error(
                    f"Library '{library_id}': "
                    f"Invalid library structure at '{library_path}'. "
                    f"Expected either '__init__.py' (flat) or "
                    f"'pyproject.toml' with nested modules (package)."
                )
                
        except Exception as e:
            logger.error(f"Library '{library_id}': Error checking library structure: {e}")

        return module_paths    

    def _load_library_class(
        self, library_folder_name: str, library_path: str
    ) -> type[BaseLibrary]:
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
                        f"Check if @library decorator is applied to the class in "
                        f"'__init__.py' at '{library_path}'"
                    )
            else:
                logger.error(
                    f"Library with folder name '{library_folder_name}': "
                    f"Missing valid 'Library' class in '__init__.py' at '{library_path}'")
                
        except Exception as e:
            logger.error(
                f"Library {library_folder_name}: "
                f"Failed instantiating {e} \n {traceback.format_exc()}")
            raise LibraryLoadError(f"Failed instantiating library {library_folder_name}: {e}")

    def _load_module_and_metadata(
        self, library_id: str, library_path: str
    ) -> Optional[ModuleType]:
        """
        Load module from a library's __init__.py.
        Handles both flat and package structures automatically.
        """
        module = None
        parent_dir_added = False
        
        # Determine the proper module path for import
        # Check if this is a core library (in src/haywire/libraries/)
        if 'src/haywire/libraries' in library_path:
            # For core libraries, use the haywire.libraries.X import path (flat structure)
            module_path = f"haywire.libraries.{library_id}"
        else:
            # For external libraries, check structure type
            flat_init = os.path.join(library_path, '__init__.py')
            package_init = os.path.join(library_path, library_id, '__init__.py')
            
            parent_dir = os.path.dirname(library_path)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
                parent_dir_added = True
            
            # Determine if flat or package structure
            if os.path.exists(flat_init):
                # Flat structure: import library_id directly
                module_path = library_id
            elif os.path.exists(package_init):
                # Package structure: import library_id.library_id
                module_path = f"{library_id}.{library_id}"
            else:
                raise ImportError(f"Could not find __init__.py for library '{library_id}'")
        
        # Import the module using the proper path
        module = importlib.import_module(module_path)
        
        # Remove from sys.path if we added it
        if parent_dir_added and 'src/haywire/libraries' not in library_path:
            parent_dir = os.path.dirname(library_path)
            if parent_dir in sys.path:
                sys.path.remove(parent_dir)
        
        return module
    
    def _discover_core_libraries(self) -> list[DiscoveredLibrary]:
        """Discover core libraries from src/haywire/libraries"""
        discovered = []
        
        if not self.core_libraries_path or not os.path.exists(self.core_libraries_path):
            logger.warning(f"Core libraries path not found: {self.core_libraries_path}")
            return discovered
        
        # Scan the core libraries directory
        lib_folders = self._scan_directory(self.core_libraries_path)
        
        for library_folder_name, library_path in lib_folders.items():
            try:
                library_cls = self._load_library_class(library_folder_name, library_path)
                identity = library_cls.class_identity
                
                discovered.append(DiscoveredLibrary(
                    identity=identity,
                    library_cls=library_cls,
                    library_path=Path(library_path),
                    install_type=InstallType.FOLDER,
                    entry_point_name=None
                ))
            except Exception as e:
                logger.error(f"Failed to load core library '{library_folder_name}': {e}")
        
        return discovered
    
    def _discover_folder_libraries(self) -> list[DiscoveredLibrary]:
        """Discover libraries from manual folder paths"""
        discovered = []
        
        for search_path in self._library_root_paths:
            # Skip core libraries path if it's in the list
            if (
                self.load_core_libraries and
                self.core_libraries_path and
                os.path.samefile(search_path, self.core_libraries_path)
            ):
                continue
            
            lib_folders = self._scan_directory(search_path)
            
            for library_folder_name, library_path in lib_folders.items():
                try:
                    library_cls = self._load_library_class(library_folder_name, library_path)
                    identity = library_cls.class_identity
                    
                    discovered.append(DiscoveredLibrary(
                        identity=identity,
                        library_cls=library_cls,
                        library_path=Path(library_path),
                        install_type=InstallType.FOLDER,
                        entry_point_name=None
                    ))
                except Exception as e:
                    logger.error(f"Failed to load folder library '{library_folder_name}': {e}")
        
        return discovered
    
    def _instantiate_libraries(self, discovered: Dict[str, DiscoveredLibrary]) -> Dict[str, BaseLibrary]:
        """Instantiate all discovered libraries"""
        instantiated = {}
        
        for lib_id, lib_info in discovered.items():
            # Skip if already instantiated
            if lib_id in self._libraries:
                continue
            
            try:
                # Instantiate the library
                library_instance = lib_info.library_cls(
                    str(lib_info.library_path),
                    self.enforce_file_watching,
                    self.debounce_delay
                )
                
                instantiated[lib_id] = library_instance
                
                # Track the source, install type, and distribution name
                self._library_sources[lib_id] = str(lib_info.library_path)
                self._library_install_types[lib_id] = lib_info.install_type
                if lib_info.distribution_name:
                    self._library_distribution_names[lib_id] = lib_info.distribution_name
                
            except Exception as e:
                logger.error(
                    f"Failed to instantiate library '{lib_info.identity.label}': {e}\n"
                    f"{format_external_exception()}"
                )
        
        return instantiated
    
    def _register_library_instance(self, library_instance: BaseLibrary):
        """Register a single library instance"""
        try:
            # Add registries to the library
            for reg_cls, ref_i in self._class_registries.items():
                library_instance.add_registry(reg_cls, ref_i)
            
            # Register the library
            self._register(library_instance)
            
            logger.info(
                f"  ✓ Registered library: '{library_instance.identity.label}' "
                f"(deps: {library_instance.identity.dependencies})"
            )
        
        except Exception as e:
            logger.error(
                f"Failed to register library '{library_instance.identity.label}': {e}\n"
                f"{format_external_exception()}"
            )
    
    def _cleanup_removed_libraries(self, current_discovered: Dict[str, DiscoveredLibrary]):
        """Remove libraries that are no longer discovered"""
        current_lib_ids = set(current_discovered.keys())
        registered_lib_ids = set(self._libraries.keys())
        
        removed_lib_ids = registered_lib_ids - current_lib_ids
        
        if removed_lib_ids:
            logger.info("\n🗑  Removing unregistered libraries...")
            
        for library_id in removed_lib_ids:
            library_instance = self._libraries.get(library_id)
            if library_instance:
                logger.info(
                    f"  ⊘ Removing library '{library_instance.identity.label}'"
                )
                
                # Disable and unregister
                library_instance.disable()
                self._unregister(library_id)
                
                # Remove from sources tracking
                if library_id in self._library_sources:
                    del self._library_sources[library_id]
                if library_id in self._library_distribution_names:
                    del self._library_distribution_names[library_id]
    
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
    
    def get_library_source(self, library_id: str) -> str | None:
        """Get the source path for a library"""
        return self._library_sources.get(library_id)
    
    def get_library_install_type(self, library_id: str) -> InstallType | None:
        """Get the install type for a library"""
        return self._library_install_types.get(library_id)

    def get_library_distribution_name(self, library_id: str) -> str | None:
        """Get the pip distribution name for a library (e.g. 'haybale-visiongraph')"""
        return self._library_distribution_names.get(library_id)

