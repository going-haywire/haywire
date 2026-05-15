"""Module reloaded by test_hot_reload_roundtrip.py.

Holds a minimal SignalSource so the test can exercise the reload path
without setting up a full Session/Container."""

from haywire.core.session.signals import Signal, SignalSource, signal_field
from haywire.core.session.signals.descriptor import _seed_signal_fields


class MyState(SignalSource):
    """Minimal SignalSource for the hot-reload test.

    Bypasses SessionState/AppState: those bases require a Session or
    SessionManager weakref stamped by LibraryStateContainer before
    _signal_emit can deref. The test only needs the synthetic-signal
    + bus-publish path, so we inherit SignalSource directly and pass
    in a bus.
    """

    x: int = signal_field(0)

    def __init__(self, bus):
        self._bus = bus
        _seed_signal_fields(self)

    def _signal_emit(self, signal: Signal) -> None:
        self._bus.publish(signal)
