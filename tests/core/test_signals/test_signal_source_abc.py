"""Tests for SignalSource — the ABC contract for hosts that emit signals."""

import pytest
from haywire.core.session.signals import SignalSource, Signal


def test_signal_source_is_abstract():
    """A class inheriting SignalSource without implementing _signal_emit
    cannot be instantiated."""

    class Incomplete(SignalSource):
        pass

    with pytest.raises(TypeError) as ei:
        Incomplete()  # type: ignore[abstract]
    assert "abstract" in str(ei.value).lower()


def test_signal_source_concrete_implementation_works():
    """An implementor with _signal_emit is instantiable."""
    received = []

    class Concrete(SignalSource):
        def _signal_emit(self, signal: Signal) -> None:
            received.append(signal)

    inst = Concrete()

    class Tick(Signal):
        pass

    sig = Tick()
    inst._signal_emit(sig)
    assert received == [sig]
