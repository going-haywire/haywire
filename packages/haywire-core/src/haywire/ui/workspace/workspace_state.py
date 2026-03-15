# packages/haywire-core/src/haywire/ui/workspace/workspace_state.py
"""
Workspace state dataclasses for the Haywire UI layout system.

WorkspaceState is serializable to JSON for persistence. Each named workspace
is a saved instance of this class.

All editor_key values are full registry_key strings
(e.g. 'studio:editor:graph_editor'), not short registry_id values.
This avoids collisions between editors from different libraries that share
the same short id.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

# Canonical registry keys for all built-in editors.
# Using constants avoids scattered hardcoded strings.
_K_GRAPH_EDITOR    = 'studio:editor:graph_editor'
_K_LIBRARY_BROWSER = 'studio:editor:library_browser'
_K_LIBRARY_DETAIL  = 'studio:editor:library_detail'
_K_COMPONENT_DETAIL = 'studio:editor:component_detail'
_K_PROPERTIES      = 'studio:editor:properties'
_K_CONSOLE         = 'studio:editor:console'
_K_FILE_BROWSER    = 'studio:editor:file_browser'
_K_FILE_VIEWER     = 'studio:editor:file_viewer'
_K_GRAPH_MANAGER   = 'studio:editor:graph_manager'


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
    editor_key: str = _K_GRAPH_EDITOR
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
        bottom_editor_key: Full registry_key of the editor in the bottom split.
    """
    tabs: List[TabState] = field(default_factory=lambda: [TabState()])
    active_tab_index: int = 0
    bottom_visible: bool = False
    bottom_size: int = 200
    bottom_editor_key: Optional[str] = _K_CONSOLE


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
    left_bar_active: Optional[str] = _K_LIBRARY_BROWSER
    left: AreaState = field(default_factory=lambda: AreaState(
        editor_key=_K_LIBRARY_BROWSER, visible=True, size=250
    ))
    middle: MiddleAreaState = field(default_factory=MiddleAreaState)
    right_bar_active: Optional[str] = _K_PROPERTIES
    right: AreaState = field(default_factory=lambda: AreaState(
        editor_key=_K_PROPERTIES, visible=True, size=350
    ))
