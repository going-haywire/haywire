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
    State of the middle (main) area which supports tabs and a bottom split.

    Attributes:
        tabs: List of open tabs.
        active_tab_index: Which tab is currently active.
        bottom_visible: Whether the bottom split area is shown.
        bottom_size: Height of the bottom area in pixels.
        bottom_editor_key: Full registry_key of the editor in the bottom split.
    """

    tabs: List[TabState] = field(default_factory=lambda: [TabState()])
    active_tab_index: int = 0
    bottom_visible: bool = False
    bottom_size: int = 200
    bottom_editor_key: Optional[str] = None


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
        middle: Middle area state (with tabs and bottom split).
        right: Right area state.
        right_bar_active: Full registry_key of the active context bar editor.
    """

    name: str = "default"
    left_bar_active: Optional[str] = None
    left: AreaState = field(default_factory=AreaState)
    middle: MiddleAreaState = field(default_factory=MiddleAreaState)
    right_bar_active: Optional[str] = None
    right: AreaState = field(default_factory=AreaState)
