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
key on the per-session bus; instance access yields the stored value; writes
auto-emit the synthetic signal.

Framework / library internals:
    SessionManager      — per-process session registry; broadcasts signals
                          across sessions
    IProjectState       — protocol the studio app implements (used by
                          editors that need to reach the project root)
    WorkspaceManager    — per-session layout snapshot (which editor in
                          which slot); persisted to workspace_state.json
"""

from .session import Session
from .session_manager import SessionManager
from .context import SessionContext
from .protocols import IProjectState
from .signals import (
    # Bases
    Signal,
    CommandSignal,
    # Transport
    SignalBus,
    SignalHandler,
    SignalSource,
    # Descriptor
    signal_field,
    # Observations
    ActiveGraphMoved,
    SelectionMoved,
    GraphDataMutated,
    LibraryCatalogChanged,
    # Imperative commands
    Reveal,
    Close,
    BroadcastClose,
)
from .handlers import redraw_on, react_on
from .workspace.manager import WorkspaceManager

__all__ = [
    # Session lifecycle
    "Session",
    "SessionManager",
    "SessionContext",
    # Protocols
    "IProjectState",
    # Bus payload bases
    "Signal",
    "CommandSignal",
    # Transport
    "SignalBus",
    "SignalHandler",
    "SignalSource",
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
