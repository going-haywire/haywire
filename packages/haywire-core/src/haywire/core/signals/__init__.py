"""Signal-field unification: signals, the bus, the host ABC, the descriptor.

Public surface:
- Signal, CommandSignal — base classes
- SignalBus, SignalHandler — the transport
- SignalSource — the host ABC
- signal_field — the descriptor factory
- Concrete signals (SelectionMoved, GraphDataMutated, ...) — the vocabulary
"""

from .signal import Signal, CommandSignal
from .bus import SignalBus, SignalHandler
from .host import SignalSource
from .dispatcher import SignalDispatcher
from .peer import SignalPeer
from .descriptor import signal_field
from .vocabulary import (
    ActiveGraphMoved,
    SelectionMoved,
    RevealGraphInstance,
    GraphDataMutated,
    GraphSaved,
    LibraryCatalogChanged,
    ErrorLogged,
    ErrorLedgerChanged,
    PresenceChanged,
    FarmhandActivity,
    RosterChanged,
    AgentConnected,
    AgentDisconnected,
    Reveal,
    Close,
    BroadcastClose,
)

__all__ = [
    # Bases
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
    # Observations
    "ActiveGraphMoved",
    "SelectionMoved",
    "RevealGraphInstance",
    "GraphDataMutated",
    "GraphSaved",
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
    "Close",
    "BroadcastClose",
]
