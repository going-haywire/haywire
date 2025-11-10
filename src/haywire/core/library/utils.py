
from pathlib import Path
import sys
import traceback
from typing import Dict, Any, Optional, Type
import re

def derive_library_id(cls: Type) -> str | None:
    """
    Derive library ID by finding the parent Library class.
    
    Walks up the module hierarchy looking for a Library class with
    class_identity.id attribute. Uses sys.modules to avoid re-importing.
    
    This function is used by decorators (@node, @renderer, @widget) to automatically
    determine the library ID from the module structure, enabling classes to know
    their full registry_key before registration.
    
    Args:
        cls: The class to find the library for
        
    Returns:
        str | None: Library ID if found, None if unable to determine
        
    Example:
        For a class at haywire.libraries.core.nodes.basic_nodes.TestNode:
        - Walks up: haywire.libraries.core.nodes -> haywire.libraries.core
        - Finds Library class in haywire.libraries.core.__init__
        - Returns 'core' from Library.class_identity.id
    """
    module_path = cls.__module__
    parts = module_path.split('.')
    
    # Walk up the module hierarchy
    for i in range(len(parts), 0, -1):
        potential_lib_path = '.'.join(parts[:i])
        
        # Only check already-imported modules to avoid side effects
        if potential_lib_path not in sys.modules:
            continue
            
        module = sys.modules[potential_lib_path]
        
        # Look for Library class with class_identity
        if hasattr(module, 'Library'):
            lib_class = getattr(module, 'Library')
            if hasattr(lib_class, 'class_identity'):
                return lib_class.class_identity.id
    
    return None

def find_repo_root():
    """Find repository root by looking for .git directory or other indicators."""
    current = Path(__file__).resolve()
    
    for parent in current.parents:
        if (parent / '.git').exists() or (parent / 'pyproject.toml').exists():
            return parent
    
    # Fallback to current file's directory
    return current.parent

def reg_key(library_registry_id: str, node_registry_id: str) -> str:
    """Generate the registry key from the library and class name."""
    camel_class_name = camel_to_dot_case(node_registry_id)
    return f"{library_registry_id}:{camel_class_name}"

def camel_to_dot_case(CamelCaseString: str) -> str:
    """Convert CamelCase to dot.case with handling of consecutive uppercase letters"""
    # Handle transition from lowercase to uppercase
    result = re.sub(r'([a-z])([A-Z])', r'\1.\2', CamelCaseString)
    # Handle transition from multiple uppercase to lowercase (e.g., "XMLHttp" -> "XML.Http")
    result = re.sub(r'([A-Z])([A-Z][a-z])', r'\1.\2', result)
    return result.lower()

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