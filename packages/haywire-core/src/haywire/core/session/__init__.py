# haywire/core/session/__init__.py
"""
Session system — per-browser session, signal vocabulary, workspace layout state.

Public API for editor / panel authors:
    from haywire.core.session import (
        Session, SessionContext,                # session lifecycle
        Signal, CommandSignal,                  # bus payload bases
        SelectionMoved, GraphDataMutated, ...,  # observation vocabulary
        Reveal, Close, BroadcastClose,          # imperative vocabulary
        signal_field,                           # signal-emitting field descriptor
    )

``signal_field`` is the unified reactive primitive: declared on bases that
inherit ``SignalSource`` (``SessionContext``, ``AppState``, ``SessionState``).
Class access yields a synthetic ``Signal`` subclass used as a subscription
key on the per-peer bus; instance access yields the stored value; writes
auto-emit the synthetic signal.

The transport itself lives in :mod:`haywire.core.signals` and is not
browser-specific: a ``Session`` is one *kind* of ``SignalPeer`` (the
browser-tab kind). Non-browser peers — an agent-facing MCP host, a CLI, a
headless embedding — join the same fan-out without a ``WorkspaceManager`` or a
``SessionContext``. The names are re-exported here for authors who already
import their signal vocabulary from this package.

Framework / library internals:
    SessionManager      — per-process registry of browser sessions; lifecycle
                          only (fan-out belongs to SignalDispatcher)
    SignalDispatcher    — cross-peer fan-out channel
    SignalPeer          — base for anything that owns a bus and joins fan-out
    IAppState           — protocol the studio app implements (used by
                          editors that need to reach the project root)
    WorkspaceManager    — per-session layout snapshot (which editor in
                          which slot); persisted to workspace_state.json
"""

from __future__ import annotations

from haywire.core.signals import (
    # Observations
    ActiveGraphMoved,
    BroadcastClose,
    Close,
    CommandSignal,
    GraphDataMutated,
    LibraryCatalogChanged,
    # Imperative commands
    Reveal,
    SelectionMoved,
    # Bases
    Signal,
    # Transport
    SignalBus,
    # Fan-out
    SignalDispatcher,
    SignalHandler,
    SignalPeer,
    SignalSource,
    # Descriptor
    signal_field,
)

from .context import SessionContext
from .handlers import react_on, redraw_on
from .protocols import IAppState
from .session import Session
from .session_manager import SessionManager
from .workspace.manager import WorkspaceManager

__all__ = [
    # Session lifecycle
    "Session",
    "SessionManager",
    "SessionContext",
    # Protocols
    "IAppState",
    # Bus payload bases
    "Signal",
    "CommandSignal",
    # Transport
    "SignalBus",
    "SignalHandler",
    "SignalSource",
    # Fan-out
    "SignalDispatcher",
    "SignalPeer",
    # Descriptor
    "signal_field",
    # Signals — focus
    "ActiveGraphMoved",
    # Signals — selection
    "SelectionMoved",
    # Signals — data
    "GraphDataMutated",
    "LibraryCatalogChanged",
    # Imperative commands
    "Reveal",
    "Close",
    "BroadcastClose",
    # Handler decorators
    "redraw_on",
    "react_on",
    # Workspace
    "WorkspaceManager",
]
