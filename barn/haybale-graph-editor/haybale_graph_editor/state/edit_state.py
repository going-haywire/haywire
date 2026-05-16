"""EditState — per-session graph-editor selection and clipboard state.

Each field is a ``signal_field``: reads/writes use bare attribute
access, identity-equal writes are no-ops, and the framework synthesizes
one ``Signal`` subclass per field at class definition::

    edit = ctx.data[EditState]
    edit.active_node = wrapper      # writes value, emits EditState.active_node
    node = edit.active_node         # reads stored value

Subscribers reference the class-level field as the signal type::

    @redraw_on(EditState.active_node)
    def _on(self, ctx, signal): ...

The field reference IS the subscription key — there is no separate
event class to import.

Hot-reload: when this file is re-imported, EditState's per-session
instance is torn down and recreated, dropping field values. Each
synthesized ``Signal`` subclass is also fresh; editor subscriptions are
re-bound during the editor teardown/recreate pass. Resetting selection
mid-session as a developer action is acceptable.

See docs/architecture/session-and-state/session-and-state-arch.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Set

from haywire.core.session.signals import signal_field
from haywire.core.state import SessionState, state

if TYPE_CHECKING:
    from haywire.core.edge.edge_wrapper import EdgeWrapper
    from haywire.core.graph.base import BaseGraph
    from haywire.core.node.base import DataPort
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
