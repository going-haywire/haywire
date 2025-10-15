import ast
import logging
import os
import importlib
import inspect
from pathlib import Path
import sys
import re
import traceback
from types import ModuleType
from typing import List, Type, Optional, Callable

from haywire.core.errors import log_detailed_error
from haywire.core.inventory.library_identity import LibraryIdentity


class FolderScanMixin:
    """Mixin class providing folder and module scanning capabilities for class registries"""
    
    def folder_scan_for_classes(self, library_path: str,
                                library_identity: LibraryIdentity,
                                class_filter: Callable[[Type], bool],
                                exclude_patterns: Optional[List[str]] = None) -> List[Type]:
        """
        Automatically discover classes in a library directory based on a filter function.

        Remarks: should only be used when the libraries are registering their
        inventory for the first time. The subsequent call of the method
        'module_scan_for_classes' does not enforce the reloading of the module,
        since this would lead to unexpected behavior when comparing the classes 
        returned by this method with the classes imported by the __init__.py file.

        Args:
            library_path: Path to the library directory to scan. Conveniently, use __path__[0]
            library_identity: Identity of the library being scanned
            class_filter: Function that returns True if a class should be included
            exclude_patterns: List of filename patterns to exclude

        Returns:
            List of discovered classes that pass the filter
        """
        if exclude_patterns is None:
            exclude_patterns = ['test_', '__', '_test']

        discovered_classes = []
        library_dir = Path(library_path)

        # Convert filesystem path to module path   
        module_prefix = self.resolve_module_name(library_dir)
        if not module_prefix:
            logging.warning(f"Could not resolve module name for {library_path}")
            return []

        for py_file in library_dir.glob('*.py'):
            # Skip __init__.py and excluded patterns
            if py_file.name == '__init__.py':
                continue

            if any(pattern in py_file.name for pattern in exclude_patterns):
                continue

            try:
                # Import the module
                module_name = f"{module_prefix}.{py_file.stem}"
                discovered_classes.extend(self.module_scan_for_classes(module_name, library_identity, class_filter, False))

            except Exception as e:
                logging.warning(f"Could not import {py_file.name}: {e} \n{traceback.format_exc()}")
                continue

        return discovered_classes

    def module_scan_for_classes(self, module_name: str, 
                                library_identity: LibraryIdentity,
                                class_filter: Callable[[Type], bool],
                                force_reload: bool = False) -> List[Type]:
        """
        Automatically discover classes in a module based on a filter function.
        
        Args:
            module_name: Name of the module to scan
            library_identity: Identity of the library being scanned
            class_filter: Function that returns True if a class should be included
            force_reload: Whether to force reload the module even if it is already imported
        
        Returns:
            List of discovered classes that pass the filter
        """
        discovered_classes = []

        if force_reload and module_name in sys.modules:
            # The existing module needs to be explicitly removed
            # to ensure it is the latest version that is reloaded
            del sys.modules[module_name]
        
        module = self._catch_import_modules(module_name, library_identity)

        # Inspect all classes in the module
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Ensure it's defined in this module (not imported)
            if obj.__module__ == module_name:
                try:
                    # Apply the class filter with error handling
                    if class_filter(obj):
                        discovered_classes.append(obj)
                except Exception as e:
                    # Log filter errors but continue discovery
                    logging.error(f"Filter error for class {name}: \n\n {e} \n")
                    continue

        return discovered_classes

    def resolve_module_name(self, file_path: str) -> Optional[str]:
        """
        Resolve module name from file path by walking up directories until no __init__.py found
        """
        file_path = Path(file_path)
        
        # Start from the file's directory
        current_dir = file_path.parent
        module_parts = [file_path.stem]  # Start with filename (without .py)
        
        # Walk up directories while __init__.py exists
        while True:
            init_file = current_dir / "__init__.py"
            if not init_file.exists():
                break
            
            module_parts.insert(0, current_dir.name)
            current_dir = current_dir.parent
        
        if not module_parts:
            return None
        
        return ".".join(module_parts)

    def _catch_import_modules(self, module_name: str, library_identity: LibraryIdentity) -> ModuleType | None:
        """
        Attempt to import a module by name, catching and logging any ImportError.
        
        Args:
            module_name: Name of the module to import
            library_identity: Identity of the library being scanned
        Returns:
            The imported module, or None if import failed
        """
        try:
            return importlib.import_module(module_name)
        except Exception as e:
            # Create detailed error with context about the module import
            detailed_error = log_detailed_error(
                exception=e,
                operation="import",
                module_name=module_name,
                library_id=getattr(library_identity, 'id', 'unknown') if library_identity else 'unknown',
                message=f"Failed to import module '{module_name}'"
            )
            raise detailed_error

    def _validate_python_file(self, file_path: str) -> bool:
        """Check if Python file compiles without syntax errors"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

        except OSError as e:
            logging.error(f"Error reading {file_path}: {e}")
            return False

        ast.parse(source_code, filename=file_path)
            
        return True
