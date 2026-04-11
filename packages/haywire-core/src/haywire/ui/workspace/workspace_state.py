# packages/haywire-core/src/haywire/ui/workspace/workspace_state.py
"""
Workspace state dataclasses for the Haywire UI layout system.

WorkspaceState is serializable to JSON for persistence. Each named workspace
is a saved instance of this class. All editor_key values are full registry_key
strings (e.g. 'studio:editor:graph_editor') supplied by the host application —
this module contains no host-specific strings.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class AreaState:
    """
    State of a single area in the workspace layout.

    Attributes:
        editor_key: Full registry_key of the editor currently in this area.
        visible: Whether the area is visible/expanded.
        size: Size in pixels (width for left/right, height for bottom).
    """

    editor_key: Optional[str] = None
    visible: bool = True
    size: int = 300


@dataclass
class TabState:
    """
    State of a single tab in the middle area.

    Attributes:
        editor_key: Full registry_key of the editor in this tab.
        label: Tab display label.
        metadata: Editor-specific state (e.g., which graph is open).
    """

    editor_key: Optional[str] = None
    label: str = "Graph"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MiddleAreaState:
    """
    State of the middle (main) area which supports tabs.

    The middle area is a tabbed editor region; each tab hosts one editor.

    Attributes:
        tabs: List of open tabs.
        active_tab_index: Which tab is currently active.
    """

    tabs: List[TabState] = field(default_factory=lambda: [TabState()])
    active_tab_index: int = 0


@dataclass
class BottomAreaState:
    """
    State of the bottom area — a tabbed editor region below the middle area
    that can retract to a bar-only state.

    The tab list itself is **not** persisted — it is auto-populated from the
    editor registry on every load (one tab per editor whose ``canvas_area``
    is ``"bottom"``). Only UI state (which tab is active, whether the content
    is expanded, and the last dragged height) survives across sessions.

    Attributes:
        tabs: Runtime-only tab list, repopulated on every load. Not persisted.
        active_tab_key: Full registry_key of the active bottom tab. Persisted;
            resolved to an index against the freshly auto-populated tab list
            on load, falling back to tab 0 if the key no longer exists.
        visible: Whether the bottom content panel is expanded. When False, the
            tab bar is still visible (as a retracted dock strip) but the
            content panel below it is hidden.
        size: Height of the expanded content panel in pixels.
    """

    tabs: List[TabState] = field(default_factory=list)
    active_tab_key: Optional[str] = None
    visible: bool = False
    size: int = 200


@dataclass
class WorkspaceState:
    """
    Complete workspace configuration.

    Serializable to JSON for persistence. Each named workspace
    is a saved instance of this class.

    Attributes:
        name: Workspace name (e.g., "Graph Editing", "Development").
        left_bar_active: Full registry_key of the active activity bar editor.
        left: Left area state.
        middle: Middle area state (tabbed editor region).
        bottom: Bottom area state (tabbed editor region, retractable).
        right: Right area state.
        right_bar_active: Full registry_key of the active context bar editor.
    """

    name: str = "default"
    left_bar_active: Optional[str] = None
    left: AreaState = field(default_factory=AreaState)
    middle: MiddleAreaState = field(default_factory=MiddleAreaState)
    bottom: BottomAreaState = field(default_factory=BottomAreaState)
    right_bar_active: Optional[str] = None
    right: AreaState = field(default_factory=AreaState)
