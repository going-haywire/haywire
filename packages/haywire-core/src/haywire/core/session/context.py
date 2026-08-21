# packages/haywire-core/src/haywire/ui/context.py
from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

from haywire.core.access import AccessTier, resolve_tier
from haywire.core.signals import Signal, SignalSource, signal_field
from haywire.core.signals.descriptor import _seed_signal_fields

if TYPE_CHECKING:
    from haywire.core.library.info import LibraryInfo
    from haywire.core.session.protocols import IAppState
    from haywire.core.session.session import Session
    from haywire.core.state.data_namespace import AppDataNamespace, SessionDataNamespace


class SessionContext(SignalSource):
    """Per-session context: holds signal fields that scoped editors and
    panels subscribe to, plus typed proxies into the app's library state.

    Reading: bare attribute access — ``ctx.active_file``.
    Writing: bare attribute access — ``ctx.active_file = new_path``.
    Identity-equal writes are no-ops.

    plain fields: session_id, app, session, app_data, date are non-reactive.

    ``ctx.data`` is a typed proxy for ``SessionState`` lookups, scoped
    to this session;
    ``ctx.app_data`` is the matching proxy for app-global ``AppState`` lookups.

    Subscribing: reference the class-level active-* field as the signal type::

        @redraw_on(SessionContext.active_file)
        def _on(self, ctx, signal): ...

    """

    # --- Plain fields (non-reactive) ---
    session_id: str
    app: "IAppState"
    session: "Session"  # set by Session.__init__ immediately after construction
    app_data: "AppDataNamespace"
    data: "SessionDataNamespace"
    principal: Optional[str]  # set by the studio page handler; None when auth is off

    # --- Signal fields ---
    active_file: Optional[Any] = signal_field(None)
    active_library: Optional["LibraryInfo"] = signal_field(None)
    active_component: Optional[str] = signal_field(None)

    active_workbench_theme_key: Optional[str] = signal_field(None)
    active_node_theme_key: Optional[str] = signal_field(None)

    def __init__(self, session_id: str, app: "IAppState") -> None:
        # Lazy import: state.data_namespace transitively imports state.base,
        # which imports session.signals (for SignalSource). Importing it at
        # module top would close the cycle: session.signals → session.context
        # → state.data_namespace → state.base → session.signals.
        from haywire.core.state.data_namespace import AppDataNamespace, SessionDataNamespace

        self.session_id = session_id
        self.app = app
        self.app_data = AppDataNamespace(app.library_state_container)
        self.data = SessionDataNamespace(app.library_state_container, session_id)
        # None means "authentication is not in play for this session" — the
        # resolver then answers ADMIN. The studio's page handler sets this from
        # the verified cookie when authentication is enabled.
        self.principal = None

        # Plain attributes set above; signal fields seeded below, so a signal-field
        # initializer can read from self.app_data or similar.
        _seed_signal_fields(self)
        # `session` is set by Session.__init__ after this constructor returns.

    def _signal_emit(self, signal: Signal) -> None:
        """Forward signal to the owning Session's bus.

        Implements SignalSource for SessionContext. self.session is set
        by Session.__init__ before SessionContext is used.
        """
        self.session.publish(signal)

    # ------------------------------------------------------------------
    # Access (ADR 0027)
    # ------------------------------------------------------------------

    def can_access(self, required: AccessTier) -> bool:
        """Whether this session's principal currently holds at least ``required``.

        Reads live authority through the resolver on every call rather than a
        tier stamped at login, so removing or demoting a principal takes effect
        on their next action with no eviction and no re-login. Use this when the
        tier arrives as data (e.g. ``editor.class_identity.access``); use
        :meth:`can_view` / :meth:`can_edit` / :meth:`can_admin` when it is literal.
        """
        return resolve_tier(self.principal).satisfies(required)

    def can_view(self) -> bool:
        """True whenever the principal holds any tier at all — the lowest gate.

        This is an authorization check, not an authentication one: it presumes
        identity was already established at the ASGI gate. With authentication
        disabled (no resolver installed, the state of every existing install)
        this is always True, including for ``principal is None``.
        """
        return self.can_access(AccessTier.VIEW)

    def can_edit(self) -> bool:
        """True for ``edit`` and ``admin``. Gates every mutating affordance."""
        return self.can_access(AccessTier.EDIT)

    def can_admin(self) -> bool:
        """True for ``admin`` only. Gates roster management and destructive tools."""
        return self.can_access(AccessTier.ADMIN)
