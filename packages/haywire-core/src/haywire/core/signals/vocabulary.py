# packages/haywire-core/src/haywire/core/signals/vocabulary.py
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
``SignalDispatcher.broadcast(...)`` instead of dispatching locally.

Library authors who declare their own signal classes that other libraries
subscribe to MUST list the signal-declaring library in their own
``LibraryIdentity.dependencies`` so hot-reload reloads them as a pair.
Without this, an ``isinstance`` check after a library reload can spuriously
return ``False`` when the subscriber holds a stale class reference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


# --8<-- [start:selection_moved]
@dataclass(frozen=True)
class SelectionMoved(Signal):
    """
    Node/edge selection moved on the canvas.

    Carries no binding_id: subscribers read the selection from the library's
    SessionState (e.g. ``ctx.data[MyLibState].selected_nodes`` /
    ``active_node``).
    """


# --8<-- [end:selection_moved]


@dataclass(frozen=True, kw_only=True)
class RevealGraphInstance(Signal):
    """Ask every open Subscriber in THIS session: "is this graph yours? If
    so, select this node/edge."

    graph_id compares against BaseGraph.graph_id directly
    """

    graph_id: str
    node_id: Optional[str] = None
    edge_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Data + lifecycle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GraphDataMutated(Signal):
    """Graph contents (nodes, edges, props) changed. Cross-session."""

    cross_session: ClassVar[bool] = True


@dataclass(frozen=True)
class GraphSaved(Signal):
    """A graph was written to disk. Cross-session.

    Additive, not a replacement for the save-path GraphDataMutated: panels
    legitimately use that one to refresh dirty markers. This one exists so
    subscribers interested in *the write itself* (a stale ``modified_at``,
    say) need not subscribe to every node edit to catch a save.

    Cross-session because a save mutates state every session shares — the
    file on disk.
    """

    cross_session: ClassVar[bool] = True


# --8<-- [start:library_catalog_changed]
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


# --8<-- [end:library_catalog_changed]


@dataclass(frozen=True)
class ErrorLogged(Signal):
    """A HaywireException was recorded in the process-wide error ledger.

    Carries no payload — subscribers re-read the ledger
    (``get_error_ledger().query(...)``). Cross-session: an error is a global
    fact, so every session's Errors editor refreshes.

    Emission does NOT come from a normal ``session.publish`` on a UI action.
    The ledger records from arbitrary threads (watchdog/scan) and is
    UI-ignorant; the studio app bridges its zero-arg listener hook to this
    signal via ``SignalDispatcher.broadcast`` (marshalled onto the event loop
    with ``call_soon_threadsafe``). Wiring lives in ``HaywireApp.on_startup``.

    Distinct from ``ErrorLedgerChanged`` (a *triage* mutation) — this fires only
    when a NEW error is recorded, and so is the signal that drives an unseen
    indicator / a new-error toast.
    """

    cross_session: ClassVar[bool] = True


@dataclass(frozen=True)
class ErrorLedgerChanged(Signal):
    """A ledger entry's triage state changed — seen / unseen / delete / mark-all.

    Carries no payload — subscribers re-read the ledger. Cross-session: the
    ``seen`` flag lives on the process-wide ledger, so every session's Errors
    editor must agree.

    Unlike ``ErrorLogged`` (which fires from the thread-bridge when a new error
    is recorded), this is published directly via ``session.publish`` from a UI
    action on the main loop — no new error occurred, so nothing that reacts to
    "a new error arrived" should key off it.
    """

    cross_session: ClassVar[bool] = True


@dataclass(frozen=True)
class PresenceChanged(Signal):
    """Who is connected has changed — a session opened or closed.

    Cross-session like :class:`ErrorLogged`: every shell shows the same
    presence row, so a connect in one tab must refresh the others. Carries no
    payload; subscribers re-read the live presence rather than trusting a
    snapshot that may already be stale by the time it is delivered.
    """

    cross_session: ClassVar[bool] = True


@dataclass(frozen=True)
class FarmhandActivity(Signal):
    """An agent principal started or finished an MCP tool call.

    Cross-session like :class:`PresenceChanged`, and payload-free for the same
    reason: the tracker is the single source of truth and this signal is only a
    wake-up, so subscribers re-read the live tracker
    (``haywire.core.farmhand.activity.activity_tracker()``) instead. Carrying
    the tracker itself would be exactly as fresh and buy nothing; carrying its
    history *list* would be worse than useless, because ``resize_history()``
    rebinds that deque and a held reference silently detaches.

    Emitted by the app-side bridge that observes the tracker, not by the
    Farmhand host and not by the tools — the tracker fires a zero-arg listener
    on every state change and ``HaywireApp._wire_store_broadcasts`` turns that
    into this broadcast. Recording still happens in the host, the only layer
    that knows which principal is calling, which is what covers read-only tools
    and third-party library tools without asking either to opt in.

    Not forwarded to MCP clients — echoing an agent-caused signal back to that
    agent invites a feedback loop.
    """

    cross_session: ClassVar[bool] = True


@dataclass(frozen=True)
class RosterChanged(Signal):
    """The security document's principals or tiers changed.

    Payload-free — subscribers re-read the roster through ``RosterCache``.

    Emitted by whatever writes the document (today the roster editor in
    ``haybale-studio``). The Farmhand host subscribes and pushes
    ``tools/list_changed`` so a tier edit reaches connected agents at once.
    """

    cross_session: ClassVar[bool] = True


@dataclass(frozen=True, kw_only=True)
class AgentConnected(Signal):
    """An agent principal opened an MCP session.

    Carries ``principal`` because MCP sessions are not enumerable after the
    fact, so there is nothing for a subscriber to re-read.
    """

    cross_session: ClassVar[bool] = True

    principal: str


@dataclass(frozen=True, kw_only=True)
class AgentDisconnected(Signal):
    """An agent principal's MCP session went away.

    Fires on idle timeout (``AGENT_IDLE_TIMEOUT_SECONDS`` with no traffic),
    NOT on socket close: MCP is request-shaped, so there is no disconnect event
    to observe. Late, never early.
    """

    cross_session: ClassVar[bool] = True

    principal: str


# ---------------------------------------------------------------------------
# Imperative commands
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class RevealSignal(CommandSignal):
    """Base for "bring an editor to the front" commands.

    Carries what any reveal needs to land on a tab, and nothing about *which*
    editor. Two ways to say who:

    - :class:`Reveal` names the editor class outright — for callers that own
      the class and want exactly it.
    - A subclass declaring no editor is answered by whichever editor class
      declares ``@reveal_on`` for that subclass. The publisher then needs no
      import of the editor, which is what lets ``haywire-core`` ask for a
      reveal at all (see
      ``.insights/project_app_library_dependency_direction.md``).

    Attributes:
        binding_id: Optional disambiguator for multi-instance editors
            (e.g. a graph entry id, a file path). The orchestrator switches to
            the specific ``(editor_key, binding_id)`` tab rather than the first
            binding matching ``editor_key``. ``None`` means the singleton tab.
        label: Optional display label for the revealed tab. Used only
            when the reveal creates a new tab; falls back to the editor's
            ``class_identity.label`` if omitted.
    """

    binding_id: Optional[str] = None
    label: Optional[str] = None


# --8<-- [start:reveal]
@dataclass(frozen=True, kw_only=True)
class Reveal(RevealSignal):
    """Bring a named editor to the front in its default slot.

    Routed point-to-point: the AppShell resolves
    ``editor.class_identity.default_slot`` and dispatches to that slot.
    If the slot is not hostable in the active workspace, the reveal is
    dropped with a warning.

    Attributes:
        editor: The editor class to reveal.
        binding_id: See :class:`RevealSignal`.
        label: See :class:`RevealSignal`.
    """

    editor: "type[BaseEditor]"


# --8<-- [end:reveal]


@dataclass(frozen=True, kw_only=True)
class RevealComponentSource(RevealSignal):
    """Ask whoever hosts a source viewer to show this component's code.

    Names no editor: the publisher carries a registry key and whichever editor
    declares ``@reveal_on(RevealComponentSource)`` answers. That keeps the
    dependency arrow pointing the one legal way (``haybale-* ->
    haywire-studio -> haywire-core``, never the reverse; see
    ``.insights/project_app_library_dependency_direction.md``) — core can
    publish this, but could never name ``ComponentSourceEditor``.

    Published by core UI that knows a key but not an editor — a settings row's
    developer menu. Answered by ``haybale-studio``'s ``ComponentSourceEditor``,
    whose hook points ``active_component`` at the key before the reveal.

    Asks for a *component*, so only a subscriber that can resolve a registry
    key answers. To ask for a plain file instead, publish :class:`RevealSource`
    — resolve the key to a path first (``LibraryService.lookup_component_class``
    plus ``inspect.getfile``, both core-side). For the same component's
    documentation rather than its code, publish :class:`RevealComponentDocs`.

    Session-local, like ``RevealGraphInstance``: this is a personal navigation
    click and must not move a peer session's editors. Fire-and-forget — with no
    source-viewer library installed nothing answers, and that is a working
    configuration, not an error.

    Attributes:
        registry_key: The component to show, e.g. ``lib:node:MyNode``.
    """

    registry_key: str


@dataclass(frozen=True, kw_only=True)
class RevealComponentDocs(RevealSignal):
    """Ask whoever hosts a docs viewer to show this component's documentation.

    The docs-shaped sibling of :class:`RevealComponentSource`, identical in
    shape and rationale — same registry key, same editor-agnostic routing, same
    reason (core can name a key but never a barn editor class). Two signals
    rather than one with a ``mode`` field because they are answered by two
    different editors, and which editor answers is exactly what ``@reveal_on``
    dispatches on.

    Answered by ``haybale-studio``'s ``ComponentDocsEditor``.

    Session-local and fire-and-forget, like :class:`RevealComponentSource`.

    Attributes:
        registry_key: The component to document, e.g. ``lib:node:MyNode``.
    """

    registry_key: str


@dataclass(frozen=True, kw_only=True)
class RevealSource(RevealSignal):
    """Ask whoever edits files to open the file at ``binding_id``.

    Adds no fields of its own: a file editor binds its tabs BY path, so
    :attr:`RevealSignal.binding_id` already *is* the path — carrying a separate
    ``path`` would be the same string twice, free to disagree. It only narrows
    ``binding_id`` to required, since a reveal with no file to open is
    meaningless.

    The file-shaped counterpart of :class:`RevealComponentSource`, and the
    editor-agnostic counterpart of :class:`Reveal`. Answered by
    ``haybale-studio``'s ``CodeEditor``.

    Anything the code editor opens is fair game, not only source — Markdown,
    JSON, TOML, logs. A path it does not handle is simply not opened (its hook
    vetoes).

    ``Reveal(editor=CodeEditor, binding_id=...)`` stays the way to open a file
    when the caller already knows the editor class and wants exactly it; this
    is for callers that only have a path.

    Session-local and fire-and-forget, like ``RevealComponentSource``.

    Attributes:
        binding_id: Absolute path of the file to open, as a string. Required.
        label: See :class:`RevealSignal`; falls back to the file's name.
    """

    # ``field()`` with no default, not a bare re-annotation: re-annotating
    # inherits the base's ``= None``, which types as ``str`` but still
    # constructs as None at runtime. This makes the requirement real.
    binding_id: str = field()


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
    "RevealGraphInstance",
    "GraphDataMutated",
    "LibraryCatalogChanged",
    "ErrorLogged",
    "ErrorLedgerChanged",
    "PresenceChanged",
    "FarmhandActivity",
    "RosterChanged",
    "AgentConnected",
    "AgentDisconnected",
    # Imperative commands
    "RevealSignal",
    "Reveal",
    "RevealComponentSource",
    "RevealComponentDocs",
    "RevealSource",
    "Close",
    "BroadcastClose",
]
