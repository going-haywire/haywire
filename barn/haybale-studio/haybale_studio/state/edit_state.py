"""EditState — per-session graph-editor selection and clipboard state.

Owns the reactive cluster previously held on SessionContext. Migrated
out of haywire-core in v1.2 because (a) it is editor-specific, not
framework-level, and (b) it should participate in the v1.1 SessionState
mechanism like any other per-session library runtime state.

Read paths:
    edit = ctx.data[EditState]
    if edit.active_node.value is not None:
        ...

Write paths (only in haybale-studio editors and canvas handlers):
    ctx.data[EditState].active_node.value = wrapper

Note on hot-reload: per docs/documentation/architecture/session_state.md
§3.4, a CLASS_RELOADED event for EditState re-instantiates per-session
state, dropping field values. Editing this file is a developer action;
resetting selection mid-session is acceptable.

See docs/documentation/architecture/session_state.md.
"""

from __future__ import annotations

from copy import copy
from typing import TYPE_CHECKING, Any, Optional, Set

from haywire.core.state import SessionState
from haywire.ui.reactive import Reactive, iter_reactive_fields, reactive_field

if TYPE_CHECKING:
    from haywire.core.edge.edge_wrapper import EdgeWrapper
    from haywire.core.graph.base import BaseGraph
    from haywire.core.node.base import DataPort
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.core.undo.actions.graph_actions import ClipboardData


class EditState(SessionState):
    """Per-session graph-editor state: selection, active items, clipboard."""

    active_graph: Reactive[Optional["BaseGraph"]] = reactive_field(None)
    active_graph_path: Reactive[Optional[Any]] = reactive_field(None)

    active_node: Reactive[Optional["NodeWrapper"]] = reactive_field(None)
    active_edge: Reactive[Optional["EdgeWrapper"]] = reactive_field(None)
    active_port: Reactive[Optional["DataPort"]] = reactive_field(None)

    selected_nodes: Reactive[Set[str]] = reactive_field(set())
    selected_edges: Reactive[Set[str]] = reactive_field(set())

    clipboard: Reactive[Optional["ClipboardData"]] = reactive_field(None)

    def __init__(self) -> None:
        # Initialize per-instance Reactive[T] containers for every
        # reactive_field() descriptor. Mutable defaults (e.g. set())
        # are deep-copied per-instance to avoid sharing across sessions.
        # Same pattern SessionContext uses (see haywire/ui/context.py).
        for name, initial in iter_reactive_fields(type(self)):
            self.__dict__[name] = Reactive(copy(initial))
