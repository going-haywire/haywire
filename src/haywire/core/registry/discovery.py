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

from .base import BaseLibrary, LibraryMetadata
from .registry import LibraryRegistry, WidgetRegistry, AdapterRegistry, GadgetsRegistry

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
    
    REQUIRED_SUBDIRS = ['nodes', 'widgets', 'adapters', 'gadgets']
    
    def __init__(self):
        self.library_paths: List[str] = []
        self.discovered_libraries: Dict[str, Dict[str, Any]] = {}
    
    def add_library_path(self, path: str):
        """Add a path to search for libraries"""
        if os.path.exists(path) and os.path.isdir(path):
            self.library_paths.append(os.path.abspath(path))
            logger.info(f"Added library search path: {path}")
        else:
            logger.warning(f"Library path does not exist: {path}")
    
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
            logger.error(f"Error scanning directory {directory}: {e}")
    
    def _check_library_structure(self, library_name: str, library_path: str):
        """Check if a directory follows the required library structure"""
        try:
            # Check for required subdirectories
            missing_dirs = []
            for subdir in self.REQUIRED_SUBDIRS:
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
                logger.info(f"Valid library found: {library_name} at {library_path}")
            else:
                logger.warning(f"Invalid library structure: {library_name} (missing: {missing_dirs})")
                
        except Exception as e:
            logger.error(f"Error checking library structure for {library_name}: {e}")
    
    def _load_library_metadata(self, library_path: str) -> Optional[LibraryMetadata]:
        """Load metadata from a library's __init__.py"""
        try:
            # Determine the proper module path for import
            library_name = os.path.basename(library_path)
            
            # Check if this is a core library (in src/haywire/libraries/)
            if 'src/haywire/libraries' in library_path:
                # For core libraries, use the haywire.libraries.X import path
                module_path = f"haywire.libraries.{library_name}"
            else:
                # For external libraries, add parent to sys.path and import directly
                parent_dir = os.path.dirname(library_path)
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)
                module_path = library_name
            
            # Import the module using the proper path
            module = importlib.import_module(module_path)
            
           # Extract metadata
            if hasattr(module, 'LIBRARY_METADATA'):
                metadata_dict = module.LIBRARY_METADATA
                
                # Create LibraryMetadata with all possible fields
                # Get the actual LibraryMetadata class to inspect its fields
                from dataclasses import fields
                metadata_fields = {field.name for field in fields(LibraryMetadata)}
                
                # Build kwargs only with fields that exist in LibraryMetadata
                metadata_kwargs = {}
                for field_name in metadata_fields:
                    if field_name in metadata_dict:
                        metadata_kwargs[field_name] = metadata_dict[field_name]
                    # Set reasonable defaults for missing required fields
                    elif field_name == 'name':
                        metadata_kwargs[field_name] = library_name
                    elif field_name == 'version':
                        metadata_kwargs[field_name] = '0.0.0'
                    elif field_name == 'description':
                        metadata_kwargs[field_name] = f'Library: {library_name}'
                    elif field_name == 'author':
                        metadata_kwargs[field_name] = 'Unknown'
                    elif field_name == 'dependencies':
                        metadata_kwargs[field_name] = []

                return LibraryMetadata(**metadata_kwargs)
            
        except Exception as e:
            logger.error(f"Error loading metadata from {library_path}: {e}")
        finally:
            # Remove from sys.path if we added it
            if 'src/haywire/libraries' not in library_path:
                parent_dir = os.path.dirname(library_path)
                if parent_dir in sys.path:
                    sys.path.remove(parent_dir)
        
        return None
    
    def load_libraries(self, 
                      library_registry: LibraryRegistry,
                      widget_registry: WidgetRegistry, 
                      adapter_registry: AdapterRegistry,
                      gadgets_registry: GadgetsRegistry,
                      node_registry) -> List[str]:
        """
        Load all discovered valid libraries.
        Returns list of successfully loaded library names.
        """
        loaded_libraries = []
        
        # First discover all libraries
        self.discover_libraries()
        
        # Filter to valid libraries only
        valid_libraries = {
            name: info for name, info in self.discovered_libraries.items() 
            if info['valid']
        }
        
        # Sort by dependencies (simple approach - load core first, then others)
        sorted_libraries = self._sort_libraries_by_dependencies(valid_libraries)
        
        # Load each library
        for library_name in sorted_libraries:
            try:
                library_info = valid_libraries[library_name]
                library_instance = self._load_library_instance(library_name, library_info['path'])
                
                if library_instance:
                    # Register the library
                    library_registry.register_library(
                        library_name, 
                        library_instance, 
                        library_info['path']
                    )
                    
                    # Let the library register its components
                    library_instance.register_components(
                        widget_registry, 
                        gadgets_registry,
                        adapter_registry, 
                        node_registry
                    )
                    
                    loaded_libraries.append(library_name)
                    logger.info(f"Successfully loaded library: {library_name}")
                
            except Exception as e:
                logger.error(f"Failed to load library {library_name}: {e}")
        
        return loaded_libraries
    
    def _sort_libraries_by_dependencies(self, libraries: Dict[str, Dict]) -> List[str]:
        """Simple dependency sorting - core first, then alphabetical"""
        library_names = list(libraries.keys())
        
        # Put 'core' first if it exists
        if 'core' in library_names:
            library_names.remove('core')
            library_names.insert(0, 'core')
        
        return library_names
    
    def _load_library_instance(self, library_name: str, library_path: str) -> Optional[BaseLibrary]:
        """Load a library instance from its path"""
        try:
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
                module_path = library_name
            
            # Import the module using the proper path
            module = importlib.import_module(module_path)
            
            # Look for library class
            if hasattr(module, 'Library'):
                library_class = module.Library
                if hasattr(module, 'LIBRARY_METADATA'):
                    metadata = LibraryMetadata(**module.LIBRARY_METADATA)
                    return library_class(metadata)
            
        except Exception as e:
            logger.error(f"Error loading library instance from {library_path}: {e} \n {traceback.format_exc()}")
        finally:
            # Remove from sys.path if we added it
            if 'src/haywire/libraries' not in library_path:
                parent_dir = os.path.dirname(library_path)
                if parent_dir in sys.path:
                    sys.path.remove(parent_dir)
        
        return None
