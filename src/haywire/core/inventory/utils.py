
from pathlib import Path
import sys
import traceback
from typing import Dict, Any, Optional 
import re

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