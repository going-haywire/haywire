
from pathlib import Path
from typing import Dict, Any, Optional 
import re

def camel_to_dot_case(CamelCaseString: str) -> str:
    """Convert CamelCase to dot.case with handling of consecutive uppercase letters"""
    # Handle transition from lowercase to uppercase
    result = re.sub(r'([a-z])([A-Z])', r'\1.\2', CamelCaseString)
    # Handle transition from multiple uppercase to lowercase (e.g., "XMLHttp" -> "XML.Http")
    result = re.sub(r'([A-Z])([A-Z][a-z])', r'\1.\2', result)
    return result.lower()

def resolve_module_name(file_path: str) -> Optional[str]:
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

