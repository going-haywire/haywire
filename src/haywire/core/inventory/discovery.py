"""
Library discovery and loading system
"""

import os
import sys
import importlib
from pathlib import Path
from typing import List, Dict, Optional, Any
import logging
import traceback

from .library import BaseLibrary

from .registry.renderer_reg import RendererRegistry
from .registry.adapter_reg import AdapterRegistry
from .registry.widget_reg import WidgetRegistry
from .registry.node_reg import NodeRegistry
from .registry.library_reg import LibraryRegistry

from .base import LibraryMetadata, REQUIRED_LIB_DIRS, HAYWIRE_CORE_LIB_NAME
from .file_watcher import FileWatcher

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


class LibraryDiscovery:
    """Discovers and loads libraries from multiple locations"""

    def __init__(self):
        self.library_paths: List[str] = []
        self.discovered_libraries: Dict[str, Dict[str, Any]] = {}
        self.file_watcher: Optional[FileWatcher] = None
        self.enforce_file_watching: bool = False
    
    def add_library_path(self, path: str):
        """Add a path to search for libraries"""
        if os.path.exists(path) and os.path.isdir(path):
            self.library_paths.append(os.path.abspath(path))
            logger.info(f"Added library search path: {path}")
        else:
            logger.warning(f"Library path does not exist: {path}")
        
    def enable_file_watching(self, debounce_delay: float = 0.5, force: bool = False):
        """Enable file watching for library directories"""
        if not self.file_watcher:
            self.file_watcher = FileWatcher(debounce_delay)
        self.enforce_file_watching = force
    
    def load_libraries(self, 
                      library_registry: LibraryRegistry,
                      widget_registry: WidgetRegistry, 
                      adapter_registry: AdapterRegistry,
                      renderer_registry: RendererRegistry,
                      node_registry: NodeRegistry) -> List[str]:
        """
        Load all discovered valid libraries.
        Returns list of successfully loaded library names.
        """

        # First discover all libraries
        self.discover_libraries()
        
        # Filter to valid libraries only
        valid_libraries = {
            name: info for name, info in self.discovered_libraries.items() 
            if info['valid']
        }

        Instantiated_libraries = {}

        # instantiate each libraries with its metadata
        for library_name in valid_libraries:
            try:
                library_info = valid_libraries[library_name]
                library_instance = self._load_library_instance(library_name, library_info['path'])

                # store them in the metadata name (and not the folder)
                Instantiated_libraries[library_instance.metadata.name] = library_instance

            except Exception as e:
                logger.error(f"While attempting to load library '{library_name}': \n\n {format_external_exception()}\n")

        # Sort by dependencies using the metadata dependencies
        sorted_libraries = self._sort_libraries_by_dependencies(Instantiated_libraries)

        loaded_libraries = []

        # Load each library
        for library_instance in sorted_libraries:
            try:                
                if library_instance:
                    # Register the library
                    library_registry.register_library(
                        library_instance, 
                        library_info['path']
                    )
                    
                    # Add registries to the library
                    library_instance.add_registry(type(widget_registry), widget_registry)
                    library_instance.add_registry(type(renderer_registry), renderer_registry)
                    library_instance.add_registry(type(adapter_registry), adapter_registry)
                    library_instance.add_registry(type(node_registry), node_registry)
                    
                    # Let the library register its components
                    library_instance.register_components()
                    
                    # Add to the loaded libraries list
                    loaded_libraries.append(library_instance.metadata.name)
                    logger.info(f"Successfully loaded library: '{library_instance.metadata.name}' - deps: {library_instance.metadata.dependencies}")

                    # If file watching is enabled, register the library with the watcher
                    if self.file_watcher and (self.enforce_file_watching or library_instance.metadata.file_watcher):
                        self.file_watcher.add_library(library_instance)

            except Exception as e:
                logger.error(f"Failed to load library '{library_instance.metadata.name}': {e} \n\n {format_external_exception()}\n")
        
        return loaded_libraries

    def _sort_libraries_by_dependencies(self, libraries: Dict[str, BaseLibrary]) -> List[BaseLibrary]:
        """
        Sort libraries by dependencies using topological sort.
        'haywire.core' is always first, then dependencies are resolved.
        """
        if not libraries:
            return []
        
        # Start with haywire.core if present
        sorted_libraries = []
        remaining = libraries.copy()
        
        if HAYWIRE_CORE_LIB_NAME in remaining:
            sorted_libraries.append(remaining.pop(HAYWIRE_CORE_LIB_NAME))
        
        if not remaining:
            return sorted_libraries
        
        # Simple iterative approach: process libraries whose dependencies are satisfied
        processed = {HAYWIRE_CORE_LIB_NAME}  # Track what we've already handled
        
        # Check for unmet dependencies upfront - fail fast
        unmet_deps = set()
        for lib_name, lib in remaining.items():
            dependencies = getattr(lib.metadata, 'dependencies', []) or []
            for dep in dependencies:
                if dep not in libraries and dep != HAYWIRE_CORE_LIB_NAME:
                    logger.error(f"Detecteded unmet dependencies when loading library '{lib_name}': dependencies {dependencies}")

        while remaining:
            # Find libraries whose dependencies are all satisfied
            ready = []
            for lib_name, lib in remaining.items():
                dependencies = getattr(lib.metadata, 'dependencies', []) or []

                # Only consider dependencies that exist in our library set
                relevant_deps = [dep for dep in dependencies if dep in libraries]

            # Check if all relevant dependencies have been processed
            if all(dep in processed for dep in relevant_deps):
                ready.append(lib_name)
                  
            if not ready:
                # Circular dependency detected - add all remaining libraries
                logger.warning(f"Warning: Circular dependencies detected among: {list(remaining.keys())}")
                ready = list(remaining.keys())
            
            # Add ready libraries to result
            for lib_name in ready:
                sorted_libraries.append(remaining.pop(lib_name))
                processed.add(lib_name)
        
        return sorted_libraries

    def discover_libraries(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover all libraries in registered paths.
        Returns dict with library_name -> {path, metadata, valid}
        """
        self.discovered_libraries.clear()
        
        for search_path in self.library_paths:
            logger.info(f"Scanning for libraries in: {search_path}")
            self._scan_directory(search_path)
        
        return self.discovered_libraries.copy()
    
    def _scan_directory(self, directory: str):
        """Scan a directory for library subdirectories"""
        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isdir(item_path) and not item.startswith('.') and not item.startswith('__pycache__'):
                    self._check_library_structure(item, item_path)
        except OSError as e:
            logger.error(f"Scanning library directory '{directory}': {e}")

    def _check_library_structure(self, library_name: str, library_path: str):
        """Check if a directory follows the required library structure"""
        try:
            # Check for required subdirectories
            missing_dirs = []
            for subdir in REQUIRED_LIB_DIRS:
                subdir_path = os.path.join(library_path, subdir)
                if not os.path.exists(subdir_path):
                    missing_dirs.append(subdir)
            
            # Check for __init__.py
            init_file = os.path.join(library_path, '__init__.py')
            has_init = os.path.exists(init_file)
            
            # Determine if structure is valid (don't load metadata during discovery for performance)
            is_valid = len(missing_dirs) == 0 and has_init
            
            # Store discovery results (metadata will be loaded later during actual library loading)
            self.discovered_libraries[library_name] = {
                'path': library_path,
                'valid': is_valid,
                'missing_dirs': missing_dirs,
                'has_init': has_init,
                'metadata': None  # Lazy-loaded during library loading
            }
            
            if is_valid:
                logger.info(f"Valid library found: '{library_name}' at {library_path}")
            else:
                logger.warning(f"Invalid library structure: library '{library_name}' is missing: '{missing_dirs}' - folder")
                
        except Exception as e:
            logger.error(f"Checking library structure for '{library_name}': {e}")
        
    def _load_library_instance(self, library_name: str, library_path: str) -> Optional[BaseLibrary]:
        """Load a library instance from its path"""
        # Use the existing metadata loading method to get both module and metadata
        module, metadata = self._load_module_and_metadata(library_name, library_path)
            
        if module and hasattr(module, 'Library'):
            try:
                library_class = module.Library
                return library_class(metadata, library_path)
            except Exception as e:
                logger.error(f"Failed instantiating library {library_name}: {e} \n {traceback.format_exc()}")
                raise LibraryLoadError(f"Failed instantiating library {library_name}: {e}")
        else:
            logger.error(f"Library '{library_name}' does not have a valid 'Library' class in '__init__.py' at '{library_path}'")
            raise LibraryStructureError(f"Library '{library_name}' does not have a valid 'Library' class in '{library_path}'")

    def _load_module_and_metadata(self, library_name: str, library_path: str) -> tuple[Optional[Any], LibraryMetadata]:
        """Load module and metadata from a library's __init__.py. Always returns LibraryMetadata (with defaults if needed)."""
        module = None
        parent_dir_added = False
        
        # Determine the proper module path for import
        # Check if this is a core library (in src/haywire/libraries/)
        if 'src/haywire/libraries' in library_path:
            # For core libraries, use the haywire.libraries.X import path
            module_path = f"haywire.libraries.{library_name}"
        else:
            # For external libraries, add parent to sys.path and import directly
            parent_dir = os.path.dirname(library_path)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
                parent_dir_added = True
            module_path = library_name
        
        # Import the module using the proper path
        module = importlib.import_module(module_path)
        
        # Remove from sys.path if we added it
        if parent_dir_added and 'src/haywire/libraries' not in library_path:
            parent_dir = os.path.dirname(library_path)
            if parent_dir in sys.path:
                sys.path.remove(parent_dir)
        
        # Always create metadata (from module or defaults)
        metadata = self._create_metadata(module, library_name)
        return module, metadata

    def _create_metadata(self, module: Optional[Any], library_name: str) -> LibraryMetadata:
        """Create LibraryMetadata from module or use defaults"""
        metadata_kwargs = {
            'name': library_name,
            'version': '0.0.0',
            'description': f'Library: {library_name}',
            'author': 'Unknown',
            'dependencies': []
        }
        if module and hasattr(module, 'LIBRARY_METADATA'):
            metadata_dict = module.LIBRARY_METADATA
            
            # Create LibraryMetadata with all possible fields
            from dataclasses import fields
            metadata_fields = {field.name for field in fields(LibraryMetadata)}
            
            # Fill metadata_kwargs with fields that exist in LibraryMetadata
            for field_name in metadata_fields:
                if field_name in metadata_dict:
                    metadata_kwargs[field_name] = metadata_dict[field_name]

        return LibraryMetadata(**metadata_kwargs)
    


def format_external_exception(exclude_modules=None):
    """Format the current exception, by default excluding frames from this module"""
    if exclude_modules is None:
        exclude_modules = [__name__.split('.')[-1]]  # Exclude this module
    
    exc_type, exc_value, exc_tb = sys.exc_info()
    tb_list = traceback.extract_tb(exc_tb)
    
    filtered_frames = []
    for frame in tb_list:
        # Check if frame is from excluded modules
        frame_module = frame.filename
        if not any(module in frame_module for module in exclude_modules):
            filtered_frames.append(frame)
    
    if filtered_frames:
        return ''.join(traceback.format_list(filtered_frames)) + f"\n{exc_type.__name__}: {exc_value}"
    else:
        return f"{exc_type.__name__}: {exc_value}"