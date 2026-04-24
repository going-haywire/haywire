# packages/haywire-core/src/haywire/ui/workspace/__init__.py
"""
Workspace persistence for the Haywire UI layout.

WorkspaceManager handles loading and saving the raw workspace snapshot dict.
Slot classes (IconSlot, TabSlot) own the interpretation of snapshot contents.
"""

from .manager import WorkspaceManager

__all__ = ["WorkspaceManager"]
