"""Compatibility shim — the signals package moved to :mod:`haywire.core.signals`.

The bus was never browser-specific: :class:`~haywire.core.signals.bus.SignalBus`
imports nothing but :class:`~haywire.core.signals.signal.Signal`, and nothing
under the package ever touched NiceGUI. It lived under ``core.session`` only
because :class:`~haywire.core.session.session.Session` was its sole participant.
Now that any :class:`~haywire.core.signals.peer.SignalPeer` can join the
fan-out, the path ``core.session.signals`` misnames what it holds.

This module re-exports the full public surface so that
``from haywire.core.session.signals import Signal`` keeps working. Barn
libraries install by ``git+URL`` clone against a pinned tag, so their import
paths cannot be rewritten in lockstep with core — the shim is what makes the
move a non-event for them.

New code should import from ``haywire.core.signals`` (or, for the vocabulary
and descriptor, from ``haywire.core.session`` as before — that re-export is
unchanged and is not deprecated).

Submodule paths such as ``haywire.core.session.signals.descriptor`` are NOT
served here; a module cannot host submodules. Those had no barn callers, and
the in-repo ones now import ``haywire.core.signals.descriptor`` directly.
"""

from haywire.core.signals import (
    # Bases
    Signal,
    CommandSignal,
    # Transport
    SignalBus,
    SignalHandler,
    # Host ABC
    SignalSource,
    # Descriptor
    signal_field,
    # Vocabulary
    ActiveGraphMoved,
    SelectionMoved,
    RevealGraphInstance,
    GraphDataMutated,
    LibraryCatalogChanged,
    ErrorLogged,
    ErrorLedgerChanged,
    FarmhandActivity,
    PresenceChanged,
    Reveal,
    Close,
    BroadcastClose,
)

__all__ = [
    "Signal",
    "CommandSignal",
    "SignalBus",
    "SignalHandler",
    "SignalSource",
    "signal_field",
    "ActiveGraphMoved",
    "SelectionMoved",
    "RevealGraphInstance",
    "GraphDataMutated",
    "LibraryCatalogChanged",
    "ErrorLogged",
    "ErrorLedgerChanged",
    "FarmhandActivity",
    "PresenceChanged",
    "Reveal",
    "Close",
    "BroadcastClose",
]
