
import logging
import traceback
from pathlib import Path
from typing import Callable, List, Type, Optional

from .folder_scan import module_scan_for_classes
from .library import BaseLibrary
from .utils import resolve_module_name

def folder_scan_for_classes(library_path: str,
                            library: BaseLibrary,
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

    library_identity = library.identity

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

            discovered_classes.extend(module_scan_for_classes(module_name, library_identity, class_filter, False))

        except Exception as e:
            logging.warning(f"Could not import {py_file.name}: {e} \n{traceback.format_exc()}")
            continue

    return discovered_classes