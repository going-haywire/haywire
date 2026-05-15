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
from .descriptor import signal_field
from .vocabulary import (
    ActiveGraphMoved,
    SelectionMoved,
    GraphDataMutated,
    LibraryCatalogChanged,
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
    # Descriptor
    "signal_field",
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
