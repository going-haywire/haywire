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

    SELECTION_CHANGED = auto()  # node/edge selection changed
    ACTIVE_GRAPH_CHANGED = auto()  # switched to a different graph
    MODE_CHANGED = auto()  # interaction mode changed
    EDITOR_FOCUSED = auto()  # different editor gained focus
    WORKSPACE_CHANGED = auto()  # workspace preset switched
    DATA_MUTATED = auto()  # graph data changed (node values, structure)
    LIBRARY_STATE_CHANGED = auto()  # library enabled, disabled, installed, or selected
    ACTIVE_COMPONENT_CHANGED = auto()  # component (node/widget/renderer) selected in LibraryBrowser
    FILE_SELECTED = auto()  # file selected in FileBrowserEditor
    WORKBENCH_THEME_CHANGED = auto()  # active workbench theme switched
    CONTEXT_MENU_OPENED = auto()  # context menu popup was opened
    CONTEXT_MENU_CLOSED = auto()  # context menu popup was closed
    CUSTOM = auto()  # extensible


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
        reveal_editor: Optional registry_key of an editor that should be
            surfaced as part of handling this event. The orchestrator resolves
            it to a workspace slot via the editor's ``default_slot`` and
            switches that slot before running the poll/draw cycle, so the
            revealed editor receives the same event that caused it to be
            revealed. If the editor cannot be hosted in the active workspace
            a warning is logged and the reveal is skipped.
    """

    change_type: ContextChangeType
    source_editor: Optional[str] = None
    detail: Optional[Any] = None
    reveal_editor: Optional[str] = None
