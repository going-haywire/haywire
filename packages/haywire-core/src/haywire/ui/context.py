# packages/haywire-core/src/haywire/ui/context.py
"""
Session context for the Haywire UI system.

SessionContext is the central state object that flows through the entire UI hierarchy.
Each browser session has its own instance. Analogous to Blender's bContext.

Phase 1 reactive shape: every selection/active-* field is a `Reactive[T]`
declared via `reactive_field()`. Class-level access yields a `ReactivePath`;
instance-level access yields the `Reactive[T]` container. Read values via
`.value`; write values via `.value = ...`. Phase 2 layers Subscriptions
and auto-tracking on top — no read-site changes required for Phase 2.

The `metadata` dict remains a plain dict in Phase 1; Phase 1.5 lifts
context-menu gesture state to typed fields on the host (see
spec_panel_migration.md §4).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set, TYPE_CHECKING

from haywire.ui.reactive import Reactive, iter_reactive_fields, reactive_field

if TYPE_CHECKING:
    from haywire.core.edge.edge_wrapper import EdgeWrapper
    from haywire.core.graph.base import BaseGraph
    from haywire.core.library.base import BaseLibrary
    from haywire.core.node.base import DataPort
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.core.undo.actions.graph_actions import ClipboardData
    from haywire.ui.protocols import IProjectState
    from haywire.ui.session import Session


class SessionContext:
    """
    Per-session context carrying current UI state.

    Reactive fields are accessed as `ctx.<field>.value` (read) or
    `ctx.<field>.value = ...` (write). Plain fields (`session_id`,
    `app`, `session`, `metadata`) are non-reactive.
    """

    # --- Plain fields (non-reactive) ---
    session_id: str
    app: "IProjectState"
    session: "Session"  # set by Session.__init__ immediately after construction
    metadata: Dict[str, Any]

    # --- Reactive fields ---
    active_graph: Reactive[Optional["BaseGraph"]] = reactive_field(None)
    active_node: Reactive[Optional["NodeWrapper"]] = reactive_field(None)
    active_edge: Reactive[Optional["EdgeWrapper"]] = reactive_field(None)
    active_port: Reactive[Optional["DataPort"]] = reactive_field(None)
    selected_nodes: Reactive[Set[str]] = reactive_field(set())
    selected_edges: Reactive[Set[str]] = reactive_field(set())
    workspace_name: Reactive[str] = reactive_field("default")
    active_library: Reactive[Optional["BaseLibrary"]] = reactive_field(None)
    active_component: Reactive[Optional[str]] = reactive_field(None)
    active_file: Reactive[Optional[Any]] = reactive_field(None)
    clipboard: Reactive[Optional["ClipboardData"]] = reactive_field(None)
    active_graph_path: Reactive[Optional[Any]] = reactive_field(None)
    active_workbench_theme_key: Reactive[Optional[str]] = reactive_field(None)
    active_node_theme_key: Reactive[Optional[str]] = reactive_field(None)
    context_menu_trigger: Reactive[Optional[str]] = reactive_field(None)

    def __init__(self, session_id: str, app: "IProjectState") -> None:
        self.session_id = session_id
        self.app = app
        self.metadata = {}
        # Initialize per-instance Reactive[T] containers for every
        # descriptor on this class. Default values come from
        # reactive_field(initial) declarations above. Mutable defaults
        # (e.g., set()) are deep-copied per-instance to avoid sharing.
        from copy import copy

        for name, initial in iter_reactive_fields(type(self)):
            self.__dict__[name] = Reactive(copy(initial))
        # `session` is set by Session.__init__ after this constructor returns.
