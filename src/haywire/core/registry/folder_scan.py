import logging
import os
import importlib
import inspect
import traceback
from typing import List, Type, Optional, Callable
from pathlib import Path

from haywire.core.registry.utils import resolve_module_name

def folder_scan_for_classes(library_path: str, 
                         class_filter: Callable[[Type], bool],
                         exclude_patterns: Optional[List[str]] = None) -> List[Type]:
    """
    Automatically discover classes in a library directory based on a filter function.
    
    Args:
        library_path: Path to the library directory to scan. Conveniently, use __path__[0]
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
    module_prefix = resolve_module_name(library_dir)
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

            discovered_classes.extend(module_scan_for_classes(module_name, class_filter))
                   
        except Exception as e:
            logging.warning(f"Could not import {py_file.name}: {e} \n{traceback.format_exc()}")
            continue
    
    return discovered_classes


def module_scan_for_classes(module_name: str, 
                         class_filter: Callable[[Type], bool]) -> List[Type]:
    """
    Automatically discover classes in a module based on a filter function.
    
    Args:
        module_name: Name of the module to scan
        class_filter: Function that returns True if a class should be included
    
    Returns:
        List of discovered classes that pass the filter
    """
    discovered_classes = []

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
                logging.debug(f"Filter error for class {name}: {e}")
                continue

    return discovered_classes