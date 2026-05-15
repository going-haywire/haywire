"""Tests for the Signal root class hierarchy."""

import pytest

from haywire.core.session.signals import CommandSignal, Signal, SignalBus


def test_signal_is_concrete_dataclass_base():
    """Signal is a frozen-dataclass base; concrete subclasses are instantiable."""

    class Concrete(Signal):
        pass

    inst = Concrete()
    assert isinstance(inst, Signal)


def test_command_signal_is_signal_subclass():
    assert issubclass(CommandSignal, Signal)


def test_cross_session_default_false():
    class Concrete(Signal):
        pass

    assert Concrete.cross_session is False


def test_cross_session_can_be_overridden():
    from typing import ClassVar

    class Broadcasting(Signal):
        cross_session: ClassVar[bool] = True

    assert Broadcasting.cross_session is True


def test_signal_bus_subscribe_and_publish():
    bus = SignalBus()
    received = []

    class Tick(Signal):
        pass

    bus.subscribe(Tick, lambda s: received.append(s))
    sig = Tick()
    bus.publish(sig)
    assert received == [sig]


def test_signal_bus_exact_type_match_no_subclass_routing():
    """Subscribers to Parent do NOT receive Child events."""
    bus = SignalBus()
    parent_received = []

    class Parent(Signal):
        pass

    class Child(Parent):
        pass

    bus.subscribe(Parent, lambda s: parent_received.append(s))
    bus.publish(Child())
    assert parent_received == []


def test_signal_bus_unsubscribe():
    bus = SignalBus()
    received = []

    class Tick(Signal):
        pass

    def handler(s):
        received.append(s)

    unsub = bus.subscribe(Tick, handler)
    unsub()
    bus.publish(Tick())
    assert received == []


def test_signal_bus_handler_error_isolated():
    bus = SignalBus()
    received = []

    class Tick(Signal):
        pass

    def boom(s):
        raise RuntimeError("boom")

    bus.subscribe(Tick, boom)
    bus.subscribe(Tick, lambda s: received.append(s))
    bus.publish(Tick())  # must not raise
    assert len(received) == 1


def test_signal_bus_subscribe_rejects_non_signal():
    bus = SignalBus()
    with pytest.raises(TypeError):
        bus.subscribe(int, lambda x: None)  # type: ignore[arg-type]
