"""Reading label and dependency metadata out of a library's @library decorator."""

from __future__ import annotations

import re
from pathlib import Path


def _read_library_label(module_dir: Path, fallback: str) -> str:
    """Read the label from the @library decorator in module_dir/__init__.py.

    Falls back to *fallback* if the file is missing or the field can't be found.
    """
    init_file = module_dir / "__init__.py"
    if not init_file.exists():
        return fallback
    content = init_file.read_text()
    match = re.search(r"label\s*=\s*['\"]([^'\"]+)['\"]", content)
    return match.group(1) if match else fallback


def _read_library_dependencies(module_dir: Path) -> list[str]:
    """Read dependencies from the @library decorator in module_dir/__init__.py.

    Returns pip package names (hyphens), converted from the module names
    (underscores) used in the decorator.  Returns [] if none declared.
    """
    init_file = module_dir / "__init__.py"
    if not init_file.exists():
        return []
    content = init_file.read_text()
    match = re.search(r"dependencies\s*=\s*\[([^\]]*)\]", content, re.DOTALL)
    if not match:
        return []
    raw = match.group(1)
    modules = re.findall(r"['\"]([^'\"]+)['\"]", raw)
    return [m.replace("_", "-") for m in modules]
