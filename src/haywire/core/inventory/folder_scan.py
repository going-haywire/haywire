import logging
import re
import os
import importlib
import inspect
import sys
import traceback
from types import ModuleType
from typing import List, Type, Optional, Callable
from pathlib import Path

from haywire.core.inventory.utils import resolve_module_name

def folder_scan_for_classes(library_path: str, 
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

            discovered_classes.extend(module_scan_for_classes(module_name, class_filter, False))
                   
        except Exception as e:
            logging.warning(f"Could not import {py_file.name}: {e} \n{traceback.format_exc()}")
            continue
    
    return discovered_classes


def module_scan_for_classes(module_name: str, 
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
    
    module = _catch_import_modules(module_name)

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

def _catch_import_modules(module_name: str) -> ModuleType | None:
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
        exc_type, exc_value, exc_tb = sys.exc_info()
        
        # Get the last frame where the error occurred
        while exc_tb.tb_next:
            exc_tb = exc_tb.tb_next
        
        frame = exc_tb.tb_frame
        filename = frame.f_code.co_filename
        line_number = exc_tb.tb_lineno
        
        # Try to read the actual source line with context
        try:
            with open(filename, 'r') as f:
                lines = f.readlines()
                if line_number <= len(lines):
                    error_line = lines[line_number - 1].rstrip()
                    
                    # Create detailed error output
                    logging.error(" ========= Import Failed ============")
                    logging.error(f"Module: {module_name}")
                    logging.error(f"File  : {filename}")
                    
                    # Show context lines around the error
                    context_range = 2  # Show 2 lines before and after
                    start_line = max(0, line_number - context_range - 1)
                    end_line = min(len(lines), line_number + context_range)
                    
                    for i in range(start_line, end_line):
                        line_content = lines[i].rstrip()
                        line_num = i + 1
                        
                        if line_num == line_number:
                            # This is the error line - show it with >> marker
                            logging.error(f"Source: >>line {line_num:2d}: {line_content}")
                            
                            # Try to highlight the specific error location if available
                            if hasattr(exc_value, 'offset') and exc_value.offset:
                                # For SyntaxError, we can show the exact position
                                prefix_len = len(f"Source: >>line {line_num:2d}: ")
                                spaces = ' ' * (prefix_len + exc_value.offset - 1)
                                logging.error(f"Source: >>{spaces}~~~~")
                            else:
                                # For other errors, try to highlight based on error message
                                error_msg = str(exc_value)
                                
                                # Look for strings enclosed in single quotes in the error message
                                quoted_matches = re.findall(r"'([^']+)'", error_msg)
                                
                                highlighted = False
                                for quoted_string in quoted_matches:
                                    if quoted_string in line_content:
                                        name_pos = line_content.find(quoted_string)
                                        prefix_len = len(f"line {line_num:2d}: ")
                                        spaces = ' ' * (prefix_len + name_pos)
                                        highlight = '~' * len(quoted_string)
                                        logging.error(f"Source: >>{spaces}{highlight}")
                                        highlighted = True
                                        break
                                
                                # Fallback: if no quoted strings found or matched, don't show highlighting
                                if not highlighted:
                                    logging.debug(f"Could not highlight error in line: {line_content}")
                        else:
                            # Context line - show with .. marker
                            logging.error(f"Source: ..line {line_num:2d}: {line_content}")
                    
                    logging.error(f"Error : {exc_type.__name__}: {exc_value}")
                    logging.error(" ========= Import Failed ============")
                else:
                    # Fallback to standard traceback
                    logging.error(''.join(traceback.format_exception(exc_type, exc_value, exc_tb)))
        except (IOError, OSError):
            # If we can't read the file, fall back to standard traceback
            logging.error(''.join(traceback.format_exception(exc_type, exc_value, exc_tb)))
        
        raise Exception(f"Failed to import module {module_name}: {e}")
