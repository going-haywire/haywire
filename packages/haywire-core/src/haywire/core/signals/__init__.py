"""Signal-field unification: signals, the bus, the host ABC, the descriptor.

Public surface:
- Signal, CommandSignal, EditorCommand — base classes
- SignalBus, SignalHandler — the transport
- SignalSource — the host ABC
- signal_field — the descriptor factory
- Concrete signals (SelectionMoved, GraphDataMutated, ...) — the vocabulary
"""

from __future__ import annotations

from .bus import SignalBus, SignalHandler
from .descriptor import signal_field
from .dispatcher import SignalDispatcher
from .host import SignalSource
from .peer import SignalPeer
from .signal import CommandSignal, EditorCommand, Signal
from .vocabulary import (
    ActiveGraphMoved,
    AgentConnected,
    AgentDisconnected,
    BroadcastClose,
    Close,
    Copy,
    Cut,
    Delete,
    Duplicate,
    ErrorLedgerChanged,
    ErrorLogged,
    FarmhandActivity,
    GraphDataMutated,
    GraphHistoryChanged,
    GraphSaved,
    GraphUnsavedChanged,
    LibraryCatalogChanged,
    Paste,
    PresenceChanged,
    Redo,
    Reveal,
    RevealComponentDocs,
    RevealComponentSource,
    RevealGraphInstance,
    RevealSignal,
    RevealSource,
    RosterChanged,
    Save,
    SelectAll,
    SelectionMoved,
    SubgraphNavigation,
    ToggleLock,
    ToggleStageView,
    Undo,
)

__all__ = [
    # Bases
    "Signal",
    "CommandSignal",
    "EditorCommand",
    # Transport
    "SignalBus",
    "SignalHandler",
    "SignalSource",
    # Fan-out
    "SignalDispatcher",
    "SignalPeer",
    # Descriptor
    "signal_field",
    # Observations
    "ActiveGraphMoved",
    "SelectionMoved",
    "SubgraphNavigation",
    "RevealGraphInstance",
    "GraphDataMutated",
    "GraphSaved",
    "GraphHistoryChanged",
    "GraphUnsavedChanged",
    "LibraryCatalogChanged",
    "ErrorLogged",
    "ErrorLedgerChanged",
    "PresenceChanged",
    "FarmhandActivity",
    "RosterChanged",
    "AgentConnected",
    "AgentDisconnected",
    # Imperative commands
    "Reveal",
    "RevealSignal",
    "RevealComponentSource",
    "RevealComponentDocs",
    "RevealSource",
    "Close",
    "BroadcastClose",
    # Editor commands
    "Copy",
    "Cut",
    "Paste",
    "Duplicate",
    "Delete",
    "Undo",
    "Redo",
    "Save",
    "ToggleLock",
    "ToggleStageView",
    "SelectAll",
]
