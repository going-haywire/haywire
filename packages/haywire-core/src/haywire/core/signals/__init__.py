"""Signal-field unification: signals, the bus, the host ABC, the descriptor.

Public surface:
- Signal, CommandSignal, EditorCommand — base classes
- SignalBus, SignalHandler — the transport
- SignalSource — the host ABC
- signal_field — the descriptor factory
- Concrete signals (SelectionMoved, GraphDataMutated, ...) — the vocabulary
"""

from .signal import Signal, CommandSignal, EditorCommand
from .bus import SignalBus, SignalHandler
from .host import SignalSource
from .dispatcher import SignalDispatcher
from .peer import SignalPeer
from .descriptor import signal_field
from .vocabulary import (
    ActiveGraphMoved,
    SelectionMoved,
    SubgraphNavigation,
    RevealGraphInstance,
    GraphDataMutated,
    GraphSaved,
    GraphUnsavedChanged,
    LibraryCatalogChanged,
    ErrorLogged,
    ErrorLedgerChanged,
    PresenceChanged,
    FarmhandActivity,
    RosterChanged,
    AgentConnected,
    AgentDisconnected,
    RevealSignal,
    Reveal,
    RevealComponentSource,
    RevealComponentDocs,
    RevealSource,
    Close,
    BroadcastClose,
    Copy,
    Cut,
    Paste,
    Duplicate,
    Delete,
    Undo,
    Redo,
    ToggleLock,
    ToggleStageView,
    SelectAll,
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
    "ToggleLock",
    "ToggleStageView",
    "SelectAll",
]
