"""Settings promotion channel: listeners hear promote, demote and a restore that changes a field."""

import pytest

from haywire.barn.builtin.types import INT
from haywire.core.settings import NodeSettings, setting
from haywire.core.types.enums import PortType

pytestmark = pytest.mark.unit


class _Bag(NodeSettings):
    a = setting[INT](1)
    b = setting[INT](2, promote_default=PortType.OUTLET)


def _heard(bag: _Bag) -> list[tuple[str, PortType | None]]:
    events: list[tuple[str, PortType | None]] = []
    bag._subscribe_promotion(lambda name, direction: events.append((name, direction)))
    return events


def test_promote_and_demote_are_announced():
    bag = _Bag()
    events = _heard(bag)
    bag._set_promoted("a", PortType.CONFIG)
    bag._clear_promoted("a")
    assert events == [("a", PortType.CONFIG), ("a", None)]


def test_no_change_is_silent():
    bag = _Bag()
    events = _heard(bag)
    bag._set_promoted("b", PortType.OUTLET)  # already promoted that way
    bag._clear_promoted("a")  # not promoted
    assert events == []


def test_a_new_direction_is_announced():
    bag = _Bag()
    events = _heard(bag)
    bag._set_promoted("b", PortType.CONFIG)
    assert events == [("b", PortType.CONFIG)]


def test_restore_announces_only_what_changes():
    bag = _Bag()
    events = _heard(bag)
    bag._from_dict({"values": {}, "promoted": {"a": {"direction": "inlet"}}})
    assert sorted(events, key=lambda e: e[0]) == [("a", PortType.INLET), ("b", None)]


def test_unsubscribe_and_cleanup_stop_announcements():
    bag = _Bag()
    events: list = []

    def listener(name, direction):
        events.append(name)

    bag._subscribe_promotion(listener)
    bag._unsubscribe_promotion(listener)
    bag._set_promoted("a", PortType.CONFIG)
    bag._subscribe_promotion(listener)
    bag._cleanup()
    bag._clear_promoted("a")
    assert events == []
