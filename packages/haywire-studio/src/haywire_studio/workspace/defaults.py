# packages/haywire-studio/src/haywire_studio/workspace/defaults.py
"""
Studio-specific workspace preset defaults.

All editor registry key constants for haywire-studio editors live here.
WorkspaceManager in haywire.ui accepts these as initial_presets at construction.
"""

from typing import Dict

from haywire.ui.workspace.workspace_state import (
    WorkspaceState,
    AreaState,
    MiddleAreaState,
    TabState,
)

# Canonical registry keys for all built-in studio editors.
_K_GRAPH_EDITOR = "studio:editor:graph_editor"
_K_LIBRARY_BROWSER = "studio:editor:library_browser"
_K_LIBRARY_DETAIL = "studio:editor:library_detail"
_K_COMPONENT_DETAIL = "studio:editor:component_detail"
_K_PROPERTIES = "studio:editor:properties"
_K_CONSOLE = "studio:editor:console"
_K_FILE_BROWSER = "studio:editor:file_browser"
_K_FILE_VIEWER = "studio:editor:file_viewer"
_K_GRAPH_MANAGER = "studio:editor:graph_manager"


DEFAULT_PRESETS: Dict[str, WorkspaceState] = {
    "Graph Editing": WorkspaceState(
        name="Graph Editing",
        left_bar_active=_K_LIBRARY_BROWSER,
        left=AreaState(editor_key=_K_LIBRARY_BROWSER, visible=True, size=250),
        middle=MiddleAreaState(
            tabs=[
                TabState(editor_key=_K_GRAPH_EDITOR, label="Graph"),
                TabState(editor_key=_K_LIBRARY_DETAIL, label="Library"),
                TabState(editor_key=_K_FILE_VIEWER, label="File"),
            ],
            active_tab_index=0,
            bottom_visible=False,
        ),
        right_bar_active=_K_PROPERTIES,
        right=AreaState(editor_key=_K_PROPERTIES, visible=True, size=350),
    ),
    "Development": WorkspaceState(
        name="Development",
        left_bar_active=_K_LIBRARY_BROWSER,
        left=AreaState(editor_key=_K_LIBRARY_BROWSER, visible=True, size=250),
        middle=MiddleAreaState(
            tabs=[
                TabState(editor_key=_K_GRAPH_EDITOR, label="Graph"),
                TabState(editor_key=_K_LIBRARY_DETAIL, label="Library"),
                TabState(editor_key=_K_FILE_VIEWER, label="File"),
            ],
            active_tab_index=0,
            bottom_visible=True,
            bottom_size=200,
            bottom_editor_key=_K_CONSOLE,
        ),
        right_bar_active=_K_PROPERTIES,
        right=AreaState(editor_key=_K_PROPERTIES, visible=True, size=350),
    ),
    "Debugging": WorkspaceState(
        name="Debugging",
        left_bar_active=_K_LIBRARY_BROWSER,
        left=AreaState(editor_key=_K_LIBRARY_BROWSER, visible=False, size=250),
        middle=MiddleAreaState(
            tabs=[
                TabState(editor_key=_K_GRAPH_EDITOR, label="Graph"),
                TabState(editor_key=_K_LIBRARY_DETAIL, label="Library"),
                TabState(editor_key=_K_FILE_VIEWER, label="File"),
            ],
            active_tab_index=0,
            bottom_visible=True,
            bottom_size=300,
            bottom_editor_key=_K_CONSOLE,
        ),
        right_bar_active=_K_PROPERTIES,
        right=AreaState(editor_key=_K_PROPERTIES, visible=True, size=350),
    ),
}
