
from pathlib import Path
from typing import Dict, Any, Optional 


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

