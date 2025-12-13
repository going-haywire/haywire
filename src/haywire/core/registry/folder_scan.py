import ast
import logging
import importlib
import inspect
from pathlib import Path
import sys
from types import ModuleType
from typing import List, Type, Optional, Callable

from haywire.core.library.identity import LibraryIdentity


class FolderScanMixin:
    """Mixin class providing folder and module scanning capabilities for class registries"""

    def folder_scan_for_pyfiles(self, library_path: str,
                                   exclude_patterns: Optional[List[str]] = None) -> List[str]:
        """
        Scan a library directory for Python files, returning filepaths.

        Args:
            library_path: Path to the library directory to scan
            exclude_patterns: List of filename patterns to exclude

        Returns:
            List of filepaths of discovered Python files
        """
        if exclude_patterns is None:
            exclude_patterns = ['test_', '__', '_test']

        file_paths = []
        library_dir = Path(library_path)

        for py_file in library_dir.glob('*.py'):
            # Skip __init__.py and excluded patterns
            if py_file.name == '__init__.py':
                continue

            if any(pattern in py_file.name for pattern in exclude_patterns):
                continue
                
            file_paths.append(py_file)

        return file_paths

    def folder_scan_for_modules(self, library_path: str,
                                   exclude_patterns: Optional[List[str]] = None) -> List[str]:
        """
        Scan a library directory for Python files, returning module names.

        Args:
            library_path: Path to the library directory to scan
            exclude_patterns: List of filename patterns to exclude

        Returns:
            List of module names for discovered Python files
        """
        if exclude_patterns is None:
            exclude_patterns = ['test_', '__', '_test']

        module_names = []
        library_dir = Path(library_path)

        # Convert filesystem path to module path   
        module_prefix = self.resolve_module_name(library_dir)
        if not module_prefix:
            logging.warning(
                f"Could not resolve module name for {library_path}. "
                "No __init__.py found in parent directories."
            )
            return []

        for py_file in library_dir.glob('*.py'):
            # Skip __init__.py and excluded patterns
            if py_file.name == '__init__.py':
                continue

            if any(pattern in py_file.name for pattern in exclude_patterns):
                continue

            if not self._validate_python_file(py_file):
                logging.warning(f"Invalid Python file: {py_file}. Skip Registering.")
                continue
                
            module_name = f"{module_prefix}.{py_file.stem}"
            module_names.append(module_name)

        return module_names

    def module_scan_for_classes(self, module_name: str, 
                                library_identity: LibraryIdentity,
                                class_filter: Callable[[Type], bool],
                                force_reload: bool = False) -> tuple[List[Type], ModuleType]:
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
        
        module = importlib.import_module(module_name)

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

        return discovered_classes, module

    def resolve_module_name(
        self,
        file_path: str,
        library_root: Optional[str] = None,
        module_prefix: Optional[str] = None
    ) -> Optional[str]:
        """
        Resolve module name from file path relative to library root.
        
        Args:
            file_path: Path to the Python file
            library_root: Library root path (folder_path from LibraryIdentity)
            module_prefix: Module name prefix to use (module_name from LibraryIdentity)
        
        Returns:
            # Fully qualified module name
            # (e.g., 'haywire.libraries.core.nodes.math_nodes' or 'example.nodes.math_nodes')
        """
        file_path = Path(file_path).resolve()
        library_root_path = Path(library_root).resolve() if library_root else None
        
        if not library_root_path or not module_prefix:
            # Fallback to old behavior if no context provided
            current_dir = file_path.parent
            module_parts = [file_path.stem]
            
            while True:
                init_file = current_dir / "__init__.py"
                if not init_file.exists():
                    break
                module_parts.insert(0, current_dir.name)
                current_dir = current_dir.parent
            
            return ".".join(module_parts) if module_parts else None
        
        # Calculate relative path from library root
        try:
            rel_path = file_path.relative_to(library_root_path)
        except ValueError:
            # File is not under library root - should not happen
            logging.error(f"File {file_path} is not under library root {library_root_path}")
            return None
        
        # Build module parts from relative path
        parts = list(rel_path.parts[:-1])  # All dirs except filename
        parts.append(rel_path.stem)  # Add filename without .py
        
        # Combine prefix with relative parts
        if parts and parts != [rel_path.stem]:  # If there are subdirectories
            return f"{module_prefix}.{'.'.join(parts)}"
        else:  # File is directly in library root
            return f"{module_prefix}.{rel_path.stem}"
   
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
