# packages/haywire-core/src/haywire/ui/context_events.py
"""
Context change events for the Haywire UI system.

When SessionContext changes, a ContextChangedEvent is broadcast so all editors
in that session can re-evaluate their panels.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional


class ContextChangeType(Enum):
    """What aspect of the context changed."""
    SELECTION_CHANGED = auto()        # node/edge selection changed
    ACTIVE_GRAPH_CHANGED = auto()     # switched to a different graph
    MODE_CHANGED = auto()             # interaction mode changed
    EDITOR_FOCUSED = auto()           # different editor gained focus
    WORKSPACE_CHANGED = auto()        # workspace preset switched
    DATA_MUTATED = auto()             # graph data changed (node values, structure)
    ACTIVE_LIBRARY_CHANGED = auto()   # library selected in LibraryBrowser
    ACTIVE_COMPONENT_CHANGED = auto() # component (node/widget/renderer) selected in LibraryBrowser
    FILE_SELECTED = auto()            # file selected in FileBrowserEditor
    WORKBENCH_THEME_CHANGED = auto()  # active workbench theme switched
    CUSTOM = auto()                   # extensible


@dataclass
class ContextChangedEvent:
    """
    Broadcast when SessionContext changes.

    Editors subscribe to these events and re-evaluate their panels
    (re-run poll(), re-render draw() if needed).

    Attributes:
        change_type: What category of change occurred.
        source_editor: Which editor originated the change (if any).
        detail: Optional additional information about the change.
    """
    change_type: ContextChangeType
    source_editor: Optional[str] = None
    detail: Optional[Any] = None
