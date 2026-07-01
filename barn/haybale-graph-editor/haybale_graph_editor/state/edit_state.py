from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Set

from haywire.core.session.signals import signal_field
from haywire.core.state import SessionState, state

if TYPE_CHECKING:
    from haywire.core.edge.edge_wrapper import EdgeWrapper
    from haywire.core.graph.base import BaseGraph
    from haywire.core.types import DataPort
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.core.undo.actions.graph_actions import ClipboardData


@state(label="Edit State")
class EditState(SessionState):
    """Per-session graph-editor state: selection, active items, clipboard."""

    active_graph: Optional["BaseGraph"] = signal_field(None)
    active_graph_path: Optional[Any] = signal_field(None)

    active_node: Optional["NodeWrapper"] = signal_field(None)
    active_edge: Optional["EdgeWrapper"] = signal_field(None)
    active_port: Optional["DataPort"] = signal_field(None)

    selected_nodes: Set[str] = signal_field(set())
    selected_edges: Set[str] = signal_field(set())

    clipboard: Optional["ClipboardData"] = signal_field(None)
