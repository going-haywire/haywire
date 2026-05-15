"""Hot-reload round-trip: a SessionState class is reloaded; subscriptions
to the old class's synthetic signal must be cleaned up via editor
teardown, and new subscriptions to the reloaded class's synthetic
signal must receive emits.

This codifies the Q15 decision: synthetic signal classes participate as
first-class Signal subclasses with no special reload handling. The
existing editor teardown/recreate path is the recovery mechanism."""

import importlib
import sys

import pytest


@pytest.fixture(autouse=True)
def _isolate_hot_reload_target():
    """Pop the test-target module from sys.modules so each test starts fresh.

    Without this, a previous test's reload state would leak into the next
    test in this file (and any future test that imports the same module).
    """
    yield
    sys.modules.pop("tests.core.test_signals._hot_reload_target", None)


def test_hot_reload_creates_fresh_signal_class():
    """Reloading the module that defines a SessionState produces a new
    class object and a new synthetic signal class. Subscribers to the
    old class's signal do NOT receive emits through the new class."""
    # Use a dedicated module for this test (added in step 6.2).
    import tests.core.test_signals._hot_reload_target as target

    OldState = target.MyState
    OldSignal = OldState.x  # synthetic Signal subclass

    # Reload.
    importlib.reload(target)
    NewState = target.MyState
    NewSignal = NewState.x

    # Different class objects.
    assert OldState is not NewState
    assert OldSignal is not NewSignal
    # Both still inherit Signal.
    from haywire.core.session.signals import Signal

    assert issubclass(OldSignal, Signal)
    assert issubclass(NewSignal, Signal)


def test_old_class_subscribers_do_not_receive_new_class_emits():
    """A handler subscribed via the bus to OldSignal does NOT fire when
    a NewState instance writes its field — and a fresh handler subscribed
    to NewSignal DOES fire. This is the end-to-end Q15 contract: hot-reload
    produces fresh subscription targets that compose normally with the bus."""
    import tests.core.test_signals._hot_reload_target as target
    from haywire.core.session.signals import SignalBus

    OldState = target.MyState
    OldSignal = OldState.x

    importlib.reload(target)
    NewState = target.MyState
    NewSignal = NewState.x

    bus = SignalBus()
    old_received = []
    new_received = []
    bus.subscribe(OldSignal, lambda s: old_received.append(s))
    bus.subscribe(NewSignal, lambda s: new_received.append(s))

    new_instance = NewState(bus)
    new_instance.x = 99  # writes the new class's field; emits NewSignal

    # Old subscriber: silent (the bus uses exact-class match).
    assert old_received == []
    # New subscriber: fires once, with a NewSignal instance.
    assert len(new_received) == 1
    assert isinstance(new_received[0], NewSignal)
