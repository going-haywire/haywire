# packages/haywire-core/src/haywire/core/session/signals.py
"""
Context signals — observation half of the session dispatch story.

``ContextSignal`` subclasses describe state moves on the session (selection
changed, active graph switched, theme swapped, etc.). Anyone may emit; anyone
may subscribe; signals fan out to every editor in the session via
``Session.signal(...)``. Routing across session boundaries is declared by the
signal class via ``cross_session: ClassVar[bool]``.

Lifecycle *commands* (``Reveal``, ``Close``, ``BroadcastClose``) live in the
sibling :mod:`haywire.core.session.lifecycles` module.

See ``internals/speculative/event_bus_redesign.md`` for the in-flight
typed-bus redesign that this file is part of (PR #1 of the staged migration).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Optional


# ---------------------------------------------------------------------------
# Subject — whose state moved
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Subject:
    """
    Identifies whose session-state a signal describes.

    Two values are meaningful:

    - ``Subject.SELF`` — signals delivered to the session that emitted them
      (and the default for purely local signals). Sentinel singleton.
    - ``Subject.peer(session_id)`` — signals stamped by the transport on
      cross-session delivery; the receiving session sees this when another
      session's state moved.

    Emit sites never set the subject. The transport
    (`SessionManager.broadcast_signal`) stamps `peer(origin_id)` on
    non-origin sessions during cross-session fan-out.
    """

    peer_id: Optional[str] = None

    SELF: ClassVar["Subject"]  # populated below

    @classmethod
    def peer(cls, session_id: str) -> "Subject":
        return cls(peer_id=session_id)


Subject.SELF = Subject(peer_id=None)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ContextSignal — base class for observations
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ContextSignal:
    """
    Base class for context-change observations.

    Subclasses describe a specific kind of state move (e.g.
    ``SelectionMoved``, ``ActiveGraphMoved``). Subscribers filter with plain
    ``isinstance(signal, SignalType)`` — there is no framework-side identity
    machinery (no ``is_a`` predicate, no qualified-name comparison).

    Cross-session routing is a class-level property: set
    ``cross_session: ClassVar[bool] = True`` on a subclass to have
    `Session.signal(...)` fan it out to every other session via
    `SessionManager.broadcast_signal`. The transport stamps
    ``subject = Subject.peer(origin_id)`` on non-origin sessions.

    Signal classes are flat by convention — one class per concern, no
    inheritance for specialisation between ``ContextSignal`` and the
    leaves. Specialisation belongs in binding_id fields.

    Library authors who declare their own signal classes that other
    libraries subscribe to MUST list the signal-declaring library in their
    own ``LibraryIdentity.dependencies`` so hot-reload reloads them as a
    pair. Without this, an ``isinstance`` check after a library reload
    can spuriously return ``False`` when the subscriber holds a stale
    class reference.

    Uses ``kw_only=True`` so subclasses can declare non-defaulted fields
    after the inherited ``subject`` default without dataclass-ordering pain.
    Construct signals with keyword args (e.g. for subclasses that
    declare their own fields).
    """

    subject: Subject = Subject.SELF
    cross_session: ClassVar[bool] = False

    def is_local(self) -> bool:
        """True if this signal describes *this* session's state."""
        return self.subject == Subject.SELF

    def is_from_peer(self) -> bool:
        """True if this signal describes a peer session's state."""
        return self.subject != Subject.SELF


# ---------------------------------------------------------------------------
# Core signal classes (per §11 mapping table)
#
# Workbench / focus
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActiveGraphMoved(ContextSignal):
    """The active graph (a library-owned SessionState field) moved."""


@dataclass(frozen=True)
class ActiveFileMoved(ContextSignal):
    """``context.active_file`` moved."""


@dataclass(frozen=True)
class ActiveLibraryMoved(ContextSignal):
    """``context.active_library`` moved (selection, not catalog mutation)."""


@dataclass(frozen=True)
class ActiveComponentMoved(ContextSignal):
    """``context.active_component`` moved."""


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SelectionMoved(ContextSignal):
    """
    Node/edge selection moved on the canvas.

    Carries no binding_id: subscribers read the selection from the library's
    SessionState (e.g. ``ctx.data[MyLibState].selected_nodes`` /
    ``active_node`` for ``Subject.SELF``), or the analogous fields on
    ``session_manager.get(peer_id).context`` for peer subjects
    (pointer-by-default rule, §6.3).
    """


# ---------------------------------------------------------------------------
# Data + lifecycle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GraphDataMutated(ContextSignal):
    """Graph contents (nodes, edges, props) changed. Cross-session."""

    cross_session: ClassVar[bool] = True


@dataclass(frozen=True)
class LibraryCatalogChanged(ContextSignal):
    """
    The set / state of installed libraries changed (install, uninstall,
    enable, disable). Cross-session — peer sessions need to refresh their
    library views.

    Distinct from ``ActiveLibraryMoved`` which is per-session selection.
    """

    cross_session: ClassVar[bool] = True


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ThemeMoved(ContextSignal):
    """Active workbench theme changed for this session. Local-only."""
