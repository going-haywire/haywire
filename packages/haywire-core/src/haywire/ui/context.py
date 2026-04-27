# packages/haywire-core/src/haywire/ui/context.py
"""
Session context for the Haywire UI system.

SessionContext is the central state object that flows through the entire UI hierarchy.
Each browser session has its own instance. Analogous to Blender's bContext.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set, Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.ui.session import Session
    from haywire.ui.protocols import IProjectState
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.core.edge.edge_wrapper import EdgeWrapper
    from haywire.core.graph.base import BaseGraph
    from haywire.core.library.base import BaseLibrary
    from haywire.core.node.base import DataPort


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
        workspace_name: Name of the active workspace preset.
        active_library: Library selected in LibraryBrowser (InstalledLibrary |
            MarketplaceEntry, or None). Drives LibraryDetailEditor.
        active_component: registry_key of the component selected in LibraryBrowser
            (format "{lib_id}:{comp_singular}:{class_name}", or None). Drives
            ComponentDetailEditor, which resolves library/class from the key.
        metadata: Extensible dict for editor-specific state.
    """

    session_id: str
    app: IProjectState  # host application (HaywireApp)
    session: Session = field(init=False)  # set by Session.__init__ immediately after construction
    active_graph: Optional["BaseGraph"] = None  # BaseGraph
    active_node: Optional["NodeWrapper"] = None  # NodeWrapper
    active_edge: Optional["EdgeWrapper"] = None  # Edge
    active_port: Optional["DataPort"] = None  # DataPort resolved from active_node.node.ports
    selected_nodes: Set[str] = field(default_factory=set)
    selected_edges: Set[str] = field(default_factory=set)
    workspace_name: str = "default"
    active_library: Optional["BaseLibrary"] = None  # InstalledLibrary | MarketplaceEntry
    active_component: Optional[str] = None  # registry_key: "{lib_id}:{comp_singular}:{class_name}"
    active_file: Optional[Any] = None  # Path to the currently viewed file
    active_graph_path: Optional[Any] = None  # Path to the currently active .haywire file
    active_workbench_theme_key: Optional[str] = None  # set by host app after session creation
    active_node_theme_key: Optional[str] = None  # set by host app after session creation
    context_menu_trigger: Optional[str] = None  # 'canvas' | 'node' | 'edge' | 'selection' | None
    metadata: Dict[str, Any] = field(default_factory=dict)
