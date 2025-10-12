import logging
import os
import importlib
import inspect
import sys
import re
from types import ModuleType
from typing import List, Type, Optional, Callable

from haywire.core.errors import log_detailed_error

def module_scan_for_classes(module_name: str, 
                            metadata: Optional[object],
                         class_filter: Callable[[Type], bool],
                         force_reload: bool = False) -> List[Type]:
    """
    Automatically discover classes in a module based on a filter function.
    
    Args:
        module_name: Name of the module to scan
        class_filter: Function that returns True if a class should be included
        force_reload: Whether to force reload the module even if it is already imported
    
    Returns:
        List of discovered classes that pass the filter
    """
    discovered_classes = []

    module = None
    
    if force_reload and module_name in sys.modules:
        # The existing module needs to be explicitly removed
        # to ensure it is the latest version that is reloaded
        del sys.modules[module_name]
    
    module = _catch_import_modules(module_name, metadata)

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

def _catch_import_modules(module_name: str, metadata: Optional[object]) -> ModuleType | None:
    """
    Attempt to import a module by name, catching and logging any ImportError.
    
    Args:
        module_name: Name of the module to import
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
            library_id=getattr(metadata, 'name', 'unknown') if metadata else 'unknown',
            message=f"Failed to import module '{module_name}'"
        )
        raise detailed_error