# packages/haywire-framework/src/haywire/ui/workspace/workspace_state.py
"""
Workspace state dataclasses for the Haywire UI layout system.

WorkspaceState is serializable to JSON for persistence. Each named workspace
is a saved instance of this class.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class AreaState:
    """
    State of a single area in the workspace layout.

    Attributes:
        editor_key: Registry key of the editor currently in this area.
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
        editor_key: Registry key of the editor in this tab.
        label: Tab display label.
        metadata: Editor-specific state (e.g., which graph is open).
    """
    editor_key: str = 'graph_editor'
    label: str = 'Graph'
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
        bottom_editor_key: Editor in the bottom split.
    """
    tabs: List[TabState] = field(default_factory=lambda: [TabState()])
    active_tab_index: int = 0
    bottom_visible: bool = False
    bottom_size: int = 200
    bottom_editor_key: Optional[str] = 'console'


@dataclass
class WorkspaceState:
    """
    Complete workspace configuration.

    Serializable to JSON for persistence. Each named workspace
    is a saved instance of this class.

    Attributes:
        name: Workspace name (e.g., "Graph Editing", "Development").
        left_bar_active: Which activity bar icon is active.
        left: Left area state.
        middle: Middle area state (with tabs and bottom split).
        right: Right area state.
        right_bar_active: Which context bar icon is active.
    """
    name: str = "default"
    left_bar_active: Optional[str] = 'library_browser'
    left: AreaState = field(default_factory=lambda: AreaState(
        editor_key='library_browser', visible=True, size=250
    ))
    middle: MiddleAreaState = field(default_factory=MiddleAreaState)
    right_bar_active: Optional[str] = 'properties'
    right: AreaState = field(default_factory=lambda: AreaState(
        editor_key='properties', visible=True, size=350
    ))
