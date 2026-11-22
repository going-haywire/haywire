from __future__ import annotations

from typing import TYPE_CHECKING, Any

from haywire.api.workbench import SessionState, signal_field, state

if TYPE_CHECKING:
    from haywire.api import DataPort, NodeWrapper
    from haywire.api.workbench import BaseGraph, RevealGraphInstance
    from haywire.core.edge.edge_wrapper import EdgeWrapper
    from haywire.core.graph.edit_route import EditRoute
    from haywire.core.undo.actions.graph_actions import ClipboardData


@state(label="Edit State", description="Per-session graph-editor state: selection, active items, clipboard.")
class EditState(SessionState):
    """Per-session graph-editor state: selection, active items, clipboard."""

    active_graph: BaseGraph | None = signal_field(None)
    active_graph_path: Any | None = signal_field(None)
    active_route: EditRoute | None = signal_field(None)
    """The edit route of the active level for this session; ``None`` before a level is on screen."""

    active_node: NodeWrapper | None = signal_field(None)
    active_edge: EdgeWrapper | None = signal_field(None)
    active_port: DataPort | None = signal_field(None)

    selected_nodes: set[str] = signal_field(set())
    selected_edges: set[str] = signal_field(set())

    clipboard: ClipboardData | None = signal_field(None)

    pending_reveal: RevealGraphInstance | None = signal_field(None)
    """A reveal for a document whose tab is being opened; the new tab carries it out when it draws.

    Set only while the ``Reveal`` that opens the tab is being published, and ``None`` otherwise.
    """
