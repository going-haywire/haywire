# haywire/core/session/__init__.py
"""
Session system — per-browser session, signals/lifecycle vocabulary, reactive
fields, workspace layout state.

Public API for editor / panel authors:
    from haywire.core.session import (
        Session, SessionContext,                # session lifecycle
        Event,                                  # bus payload base
        ContextSignal, SelectionMoved, ...,     # observation vocabulary
        Reveal, Close, BroadcastClose,          # imperative vocabulary
        Reactive, reactive_field,               # reactive fields
    )

Framework / library internals:
    SessionManager      — per-process session registry; broadcasts events
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
from .events import (
    # Bus payload base
    Event,
    # Observation marker + signals
    ContextSignal,
    ActiveFileMoved,
    ActiveLibraryMoved,
    ActiveComponentMoved,
    ActiveGraphMoved,
    SelectionMoved,
    GraphDataMutated,
    LibraryCatalogChanged,
    ThemeMoved,
    # Imperative marker + commands
    LifecycleCommand,
    Reveal,
    Close,
    BroadcastClose,
)
from .handlers import redraw_on, react_on
from .reactive import Reactive, reactive_field, iter_reactive_fields
from .reactive.path import ReactivePath
from .workspace.manager import WorkspaceManager

__all__ = [
    # Session lifecycle
    "Session",
    "SessionManager",
    "SessionContext",
    # Protocols
    "IProjectState",
    # Bus payload base
    "Event",
    # Signals — base
    "ContextSignal",
    # Signals — focus
    "ActiveFileMoved",
    "ActiveLibraryMoved",
    "ActiveComponentMoved",
    "ActiveGraphMoved",
    # Signals — selection
    "SelectionMoved",
    # Signals — data
    "GraphDataMutated",
    "LibraryCatalogChanged",
    # Signals — theme
    "ThemeMoved",
    # Lifecycle commands
    "LifecycleCommand",
    "Reveal",
    "Close",
    "BroadcastClose",
    # Event-handler decorators
    "redraw_on",
    "react_on",
    # Reactive
    "Reactive",
    "reactive_field",
    "iter_reactive_fields",
    "ReactivePath",
    # Workspace
    "WorkspaceManager",
]
