# packages/haywire-core/src/haywire/core/session/signals/vocabulary.py
"""
Concrete hand-authored signals dispatched through the per-session SignalBus.

Two flavours coexist, expressed as inheritance:

- :class:`Signal` subclasses — **observations**: "X just happened" (selection
  moved, active graph switched, theme swapped). Anyone may subscribe;
  routing is fan-out.
- :class:`CommandSignal` subclasses — **imperatives**: "do Y" (reveal an
  editor, close a tab). Conventionally one subscriber per command type (the
  AppShell), but the bus does not enforce that.

Both flavours travel through the same bus. The split is vocabulary for
authors, not type machinery in the dispatcher. Emit with
``Session.publish(signal)``; subscribe with
``Session.subscribe(SignalType, handler)``.

Cross-session routing is a class-level property: set
``cross_session: ClassVar[bool] = True`` on a subclass and
``Session.publish(...)`` delegates to
``SessionManager.broadcast(...)`` instead of dispatching locally.

Library authors who declare their own signal classes that other libraries
subscribe to MUST list the signal-declaring library in their own
``LibraryIdentity.dependencies`` so hot-reload reloads them as a pair.
Without this, an ``isinstance`` check after a library reload can spuriously
return ``False`` when the subscriber holds a stale class reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Optional, TYPE_CHECKING

from .signal import Signal, CommandSignal

if TYPE_CHECKING:
    from haywire.ui.editor.base import BaseEditor


# ---------------------------------------------------------------------------
# Workbench / focus
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActiveGraphMoved(Signal):
    """The active graph (a library-owned SessionState field) moved."""


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SelectionMoved(Signal):
    """
    Node/edge selection moved on the canvas.

    Carries no binding_id: subscribers read the selection from the library's
    SessionState (e.g. ``ctx.data[MyLibState].selected_nodes`` /
    ``active_node``).
    """


# ---------------------------------------------------------------------------
# Data + lifecycle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GraphDataMutated(Signal):
    """Graph contents (nodes, edges, props) changed. Cross-session."""

    cross_session: ClassVar[bool] = True


@dataclass(frozen=True)
class LibraryCatalogChanged(Signal):
    """
    The set / state of installed libraries changed (install, uninstall,
    enable, disable). Cross-session — peer sessions need to refresh their
    library views.

    Distinct from per-session active-library selection which lives as a
    ``signal_field`` on ``SessionContext`` (``SessionContext.active_library``).

    Note: ``SessionContext.active_library`` IS itself usable as a subscription
    key — ``@redraw_on(SessionContext.active_library)`` is the canonical
    pattern for per-session active-library handlers.
    """

    cross_session: ClassVar[bool] = True


# ---------------------------------------------------------------------------
# Imperative commands
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class Reveal(CommandSignal):
    """Bring an editor to the front in its default slot.

    Routed point-to-point: the AppShell resolves
    ``editor.class_identity.default_slot`` and dispatches to that slot.
    If the slot is not hostable in the active workspace, the reveal is
    dropped with a warning.

    Attributes:
        editor: The editor class to reveal.
        binding_id: Optional disambiguator for multi-instance editors
            (e.g. a graph entry id). The orchestrator switches to the
            specific ``(editor_key, binding_id)`` tab rather than the first
            binding matching ``editor_key``.
        label: Optional display label for the revealed tab. Used only
            when the reveal creates a new tab; falls back to
            ``editor.class_identity.label`` if omitted.
    """

    editor: "type[BaseEditor]"
    binding_id: Optional[str] = None
    label: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class Close(CommandSignal):
    """Close every tab bound to ``binding_id`` across all slots.

    Routed as fan-out: the AppShell asks every slot to close any tab whose
    binding matches ``binding_id``. Used for session-local close decisions
    (e.g. dismissing a tab from a confirmation dialog in *this* session).
    For close decisions that follow from a global fact — the underlying
    entity is gone for everyone — use :class:`BroadcastClose` instead,
    which fans out to every session.

    Attributes:
        binding_id: The binding id (e.g. a graph entry id). Slots close
            every wrapper whose binding_id matches this value.
    """

    binding_id: str


@dataclass(frozen=True, kw_only=True)
class BroadcastClose(Close):
    """Cross-session ``Close``: fan tab-close out to every session.

    Used for fact-driven imperatives where the underlying entity has gone
    away (e.g. an entry was removed from a haystack, or the haystack itself
    was torn down by a library hot-reload). Each receiving session's
    AppShell closes every wrapper whose binding_id matches; sessions with
    no matching tab are unaffected.

    Prefer ``Close`` for session-local UI actions (e.g. a confirmation
    dialog the user dismissed in this tab). ``BroadcastClose`` is the
    right choice only when the close decision follows from a global fact
    rather than a session-local interaction.
    """

    cross_session: ClassVar[bool] = True


__all__ = [
    # Observations
    "ActiveGraphMoved",
    "SelectionMoved",
    "GraphDataMutated",
    "LibraryCatalogChanged",
    # Imperative commands
    "Reveal",
    "Close",
    "BroadcastClose",
]
