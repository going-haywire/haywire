# packages/haywire-core/src/haywire/ui/context.py
"""
Session context for the Haywire UI system.

SessionContext is the central state object that flows through the entire UI hierarchy.
Each browser session has its own instance. Analogous to Blender's bContext.

Selection/active-* fields are declared via `signal_field()`. Instance-
level access reads/writes the stored value with plain attribute syntax
(`ctx.active_file = ...` / `ctx.active_file`). Class-level access
(`SessionContext.active_file`) yields the synthesized `Signal` subclass
used as a subscription key on the per-session bus.

SessionContext exposes two scope-bound proxies over the app's
LibraryStateContainer:

  - `ctx.app_data[Cls]` — AppState lookups (shared across the app).
  - `ctx.data[Cls]`     — SessionState lookups (this session's slice).

See docs/architecture/session-and-state/session-and-state-arch.md.
"""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

from haywire.core.session.signals import Signal, SignalSource, signal_field
from haywire.core.session.signals.descriptor import _seed_signal_fields

if TYPE_CHECKING:
    from haywire.core.library.info import LibraryInfo
    from haywire.core.session.protocols import IProjectState
    from haywire.core.session.session import Session
    from haywire.core.state.data_namespace import AppDataNamespace, SessionDataNamespace


class SessionContext(SignalSource):
    """Per-session context: holds signal fields that scoped editors and
    panels subscribe to, plus typed proxies into the app's library state.

    Reading: bare attribute access — ``ctx.active_file``.
    Writing: bare attribute access — ``ctx.active_file = new_path``.
    Identity-equal writes are no-ops.

    Plain fields (``session_id``, ``app``, ``session``, ``app_data``,
    ``data``) are non-reactive. ``ctx.data`` is a typed proxy over the
    app's ``LibraryStateContainer`` for ``SessionState`` lookups, scoped
    to this session; ``ctx.app_data`` is the matching proxy for
    app-global ``AppState`` lookups.

    Editor-specific reactive state (graph-editor selection, clipboard,
    etc.) does not live here — it lives on a library-owned
    ``SessionState``. See ``haybale_graph_editor.state.edit_state.EditState``;
    access via ``ctx.data[EditState].active_node``.

    ``self.session`` is set by ``Session.__init__`` immediately after
    construction; it is not safe to read inside this class's
    ``__init__``.

    Subscribing: reference the class-level field as the signal type::

        @redraw_on(SessionContext.active_file)
        def _on(self, ctx, signal): ...

    The framework synthesizes one ``Signal`` subclass per field at class
    definition; the field reference IS the subscription key. There is no
    separate event class to import.

    See docs/architecture/session-and-state/session-and-state-arch.md.
    """

    # --- Plain fields (non-reactive) ---
    session_id: str
    app: "IProjectState"
    session: "Session"  # set by Session.__init__ immediately after construction
    app_data: "AppDataNamespace"
    data: "SessionDataNamespace"

    # --- Signal fields ---
    active_file: Optional[Any] = signal_field(None)
    active_library: Optional["LibraryInfo"] = signal_field(None)
    active_component: Optional[str] = signal_field(None)

    active_workbench_theme_key: Optional[str] = signal_field(None)
    active_node_theme_key: Optional[str] = signal_field(None)

    def __init__(self, session_id: str, app: "IProjectState") -> None:
        # Lazy import: state.data_namespace transitively imports state.base,
        # which imports session.signals (for SignalSource). Importing it at
        # module top would close the cycle: session.signals → session.context
        # → state.data_namespace → state.base → session.signals.
        from haywire.core.state.data_namespace import AppDataNamespace, SessionDataNamespace

        self.session_id = session_id
        self.app = app
        self.app_data = AppDataNamespace(app.library_state_container)
        self.data = SessionDataNamespace(app.library_state_container, session_id)
        # Plain attributes set above; signal fields seeded below (after plain
        # fields are available, in case a future signal-field initializer reads
        # from self.app_data or similar).
        # Initialize per-instance storage for every signal_field descriptor
        # on this class. Default values come from signal_field(initial)
        # declarations above; mutable defaults are deep-copied per-instance.
        _seed_signal_fields(self)
        # `session` is set by Session.__init__ after this constructor returns.

    def _signal_emit(self, signal: Signal) -> None:
        """Forward signal to the owning Session's bus.

        Implements SignalSource for SessionContext. self.session is set
        by Session.__init__ before SessionContext is used.
        """
        self.session.publish(signal)
