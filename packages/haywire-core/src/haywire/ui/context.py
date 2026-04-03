# packages/haywire-core/src/haywire/ui/context.py
"""
Session context for the Haywire UI system.

SessionContext is the central state object that flows through the entire UI hierarchy.
Each browser session has its own instance. Analogous to Blender's bContext.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set, Any, Dict, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from haywire.ui.session import Session
    from haywire.ui.protocols import IProjectState
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.core.edge.edge_wrapper import EdgeWrapper
    from haywire.core.graph.base import BaseGraph
    from haywire.core.library.base import BaseLibrary


class InteractionMode(Enum):
    """Current user interaction mode."""

    IDLE = "idle"
    EDITING = "editing"  # editing node values
    CONNECTING = "connecting"  # dragging a connection
    SELECTING = "selecting"  # box selection
    PANNING = "panning"  # panning the canvas


@dataclass
class SessionContext:
    """
    Per-session context carrying current UI state.

    This is the primary mechanism for context-driven panel visibility.
    Panels receive this in their poll() and draw() methods and use it
    to decide what to show.

    Attributes:
        session_id: Unique identifier for this browser session.
        app: The host application implementing IProjectState.
        session: The owning Session object (set by Session.__init__ immediately after construction).
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
    app: IProjectState  # host application (HaywireApp)
    session: Session = field(init=False)  # set by Session.__init__ immediately after construction
    active_graph: Optional["BaseGraph"] = None  # BaseGraph
    active_node: Optional["NodeWrapper"] = None  # NodeWrapper
    active_edge: Optional["EdgeWrapper"] = None  # Edge
    selected_nodes: Set[str] = field(default_factory=set)
    selected_edges: Set[str] = field(default_factory=set)
    interaction_mode: InteractionMode = InteractionMode.IDLE
    active_editor: Optional[str] = None  # editor registry key
    workspace_name: str = "default"
    active_library: Optional["BaseLibrary"] = None  # InstalledLibrary | MarketplaceEntry
    active_component: Optional[Any] = None  # node/widget/renderer class or metadata
    active_file: Optional[Any] = None  # Path to the currently viewed file
    active_graph_path: Optional[Any] = None  # Path to the currently active .haywire file
    active_workbench_theme_key: Optional[str] = None  # set by host app after session creation
    active_node_theme_key: Optional[str] = None  # set by host app after session creation
    context_menu_trigger: Optional[str] = None  # 'canvas' | 'node' | 'edge' | 'selection' | None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Selection helpers — per-session, never shared across sessions.
    # For future collaborative multi-cursor, add a separate
    # peer_selections: Dict[str, Set[str]] alongside these fields.
    # ------------------------------------------------------------------

    def set_selection(self, nodes: Set[str], edges: Set[str]) -> None:
        """Replace the current selection entirely."""
        self.selected_nodes = set(nodes)
        self.selected_edges = set(edges)

    def clear_selection(self) -> None:
        """Deselect everything."""
        self.selected_nodes.clear()
        self.selected_edges.clear()

    def select_node(self, node_id: str, multi: bool = False) -> None:
        """Select a node, optionally extending the current selection."""
        if not multi:
            self.selected_nodes.clear()
            self.selected_edges.clear()
        self.selected_nodes.add(node_id)

    def deselect_node(self, node_id: str) -> None:
        self.selected_nodes.discard(node_id)

    def select_edge(self, edge_id: str, multi: bool = False) -> None:
        """Select an edge, optionally extending the current selection."""
        if not multi:
            self.selected_nodes.clear()
            self.selected_edges.clear()
        self.selected_edges.add(edge_id)

    def deselect_edge(self, edge_id: str) -> None:
        self.selected_edges.discard(edge_id)

    def is_node_selected(self, node_id: str) -> bool:
        return node_id in self.selected_nodes

    def is_edge_selected(self, edge_id: str) -> bool:
        return edge_id in self.selected_edges
