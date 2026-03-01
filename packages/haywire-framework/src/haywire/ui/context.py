# packages/haywire-framework/src/haywire/ui/context.py
"""
Session context for the Haywire UI system.

SessionContext is the central state object that flows through the entire UI hierarchy.
Each browser session has its own instance. Analogous to Blender's bContext.
"""

from dataclasses import dataclass, field
from typing import Optional, Set, Any, Dict
from enum import Enum


class InteractionMode(Enum):
    """Current user interaction mode."""
    IDLE = "idle"
    EDITING = "editing"          # editing node values
    CONNECTING = "connecting"    # dragging a connection
    SELECTING = "selecting"      # box selection
    PANNING = "panning"          # panning the canvas


@dataclass
class SessionContext:
    """
    Per-session context carrying current UI state.

    This is the primary mechanism for context-driven panel visibility.
    Panels receive this in their poll() and draw() methods and use it
    to decide what to show.

    Attributes:
        session_id: Unique identifier for this browser session.
        active_graph: The currently viewed graph (if any).
        active_node: The currently selected/focused node wrapper (if any).
        active_edge: The currently selected edge (if any).
        selected_nodes: Set of currently selected node IDs.
        selected_edges: Set of currently selected edge IDs.
        interaction_mode: What the user is currently doing.
        active_editor: The editor type currently focused.
        workspace_name: Name of the active workspace preset.
        active_library: Library selected in LibraryBrowser (InstalledLibrary |
            MarketplaceEntry, or None). Drives LibraryDetailEditor.
        active_component: Component selected in LibraryBrowser (node/widget/renderer
            class or metadata, or None). Drives ComponentDetailEditor.
        metadata: Extensible dict for editor-specific state.
    """
    session_id: str
    active_graph: Optional[Any] = None          # HaywireGraph
    active_node: Optional[Any] = None           # NodeWrapper
    active_edge: Optional[Any] = None           # Edge
    selected_nodes: Set[str] = field(default_factory=set)
    selected_edges: Set[str] = field(default_factory=set)
    interaction_mode: InteractionMode = InteractionMode.IDLE
    active_editor: Optional[str] = None         # editor registry key
    workspace_name: str = "default"
    active_library: Optional[Any] = None        # InstalledLibrary | MarketplaceEntry
    active_component: Optional[Any] = None      # node/widget/renderer class or metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
