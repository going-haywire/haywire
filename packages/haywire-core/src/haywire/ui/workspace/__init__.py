# packages/haywire-core/src/haywire/ui/workspace/__init__.py
"""
Workspace system for the Haywire UI layout.

WorkspaceState defines the complete workspace configuration (which editors are
in which areas, panel sizes, tab layout). WorkspaceManager handles preset
loading, saving, and switching.
"""

from .workspace_state import AreaState, TabState, MiddleAreaState, WorkspaceState
from .manager import WorkspaceManager

__all__ = [
    "AreaState",
    "TabState",
    "MiddleAreaState",
    "WorkspaceState",
    "WorkspaceManager",
]
