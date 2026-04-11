# packages/haywire-core/src/haywire/ui/workspace/__init__.py
"""
Workspace system for the Haywire UI layout.

WorkspaceState defines the complete workspace configuration (which editors are
in which slots, panel sizes, tab layout). WorkspaceManager handles loading,
saving, and auto-populating from the editor registry.
"""

from .workspace_state import (
    SlotState,
    TabState,
    MainSlotState,
    BottomSlotState,
    WorkspaceState,
)
from .manager import WorkspaceManager

__all__ = [
    "SlotState",
    "TabState",
    "MainSlotState",
    "BottomSlotState",
    "WorkspaceState",
    "WorkspaceManager",
]
