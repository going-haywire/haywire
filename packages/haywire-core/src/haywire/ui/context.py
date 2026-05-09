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

SessionContext exposes two scope-bound proxies over the app's
LibraryStateContainer:

  - `ctx.app_data[Cls]` — AppState lookups (shared across the app).
  - `ctx.data[Cls]`     — SessionState lookups (this session's slice).

See internals/documentation/architecture/session_state.md.
"""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

from haywire.ui.reactive import Reactive, iter_reactive_fields, reactive_field
from haywire.core.state.data_namespace import AppDataNamespace, SessionDataNamespace

if TYPE_CHECKING:
    from haywire.core.library.info import LibraryInfo
    from haywire.ui.protocols import IProjectState
    from haywire.ui.session import Session


class SessionContext:
    """
    Per-session context carrying current UI state.

    Reactive fields are accessed as `ctx.<field>.value` (read) or
    `ctx.<field>.value = ...` (write). Plain fields (`session_id`,
    `app`, `session`, `app_data`, `data`) are non-reactive.

    `ctx.data`     — typed proxy over the app's LibraryStateContainer for
                     SessionState lookups, scoped to this session.
    `ctx.app_data` — typed proxy over the app's LibraryStateContainer for
                     AppState lookups, shared across the whole app.

    Editor-specific reactive state (graph-editor selection, clipboard,
    etc.) does not live here — it lives on a library-owned
    ``SessionState``. See ``haybale_studio.state.edit_state.EditState``;
    access via ``ctx.data[EditState].active_node.value``.

    See internals/documentation/architecture/session_state.md.
    """

    # --- Plain fields (non-reactive) ---
    session_id: str
    app: "IProjectState"
    session: "Session"  # set by Session.__init__ immediately after construction
    app_data: AppDataNamespace
    data: SessionDataNamespace

    # --- Reactive fields ---
    active_file: Reactive[Optional[Any]] = reactive_field(None)
    active_library: Reactive[Optional["LibraryInfo"]] = reactive_field(None)
    active_component: Reactive[Optional[str]] = reactive_field(None)

    active_workbench_theme_key: Reactive[Optional[str]] = reactive_field(None)
    active_node_theme_key: Reactive[Optional[str]] = reactive_field(None)

    def __init__(self, session_id: str, app: "IProjectState") -> None:
        self.session_id = session_id
        self.app = app
        self.app_data = AppDataNamespace(app.library_state_container)
        self.data = SessionDataNamespace(app.library_state_container, session_id)
        # Initialize per-instance Reactive[T] containers for every
        # descriptor on this class. Default values come from
        # reactive_field(initial) declarations above. Mutable defaults
        # (e.g., set()) are deep-copied per-instance to avoid sharing.
        from copy import copy

        for name, initial in iter_reactive_fields(type(self)):
            self.__dict__[name] = Reactive(copy(initial))
        # `session` is set by Session.__init__ after this constructor returns.
