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
    TAB_CLOSE_REQUESTED = auto()  # editor (or caller) is asking the shell to close a tab
    TAB_REPAYLOAD_REQUESTED = auto()  # re-key a tab after save-as / rename
    GRAPH_REMOVED = auto()  # a haystack entry was removed; shell closes matching tabs
    OPEN_GRAPH_REQUESTED = auto()  # caller asks AppShell to activate an entry + reveal its tab
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
        reveal_payload: Optional disambiguator for multi-instance editors
            (e.g., a graph path). When provided alongside ``reveal_editor``
            the orchestrator switches to the specific ``(editor_key, payload)``
            tab rather than the first binding matching ``editor_key``. Absent
            or ``None`` preserves the pre-multi-instance behavior.
        reveal_label: Optional display label for the revealed tab. Used only
            when the reveal creates a new tab (e.g., opening a graph file for
            the first time). If omitted, the tab label falls back to the
            editor class's default label.
    """

    change_type: ContextChangeType
    source_editor: Optional[str] = None
    detail: Optional[Any] = None
    reveal_editor: Optional[str] = None
    reveal_payload: Optional[str] = None
    reveal_label: Optional[str] = None
