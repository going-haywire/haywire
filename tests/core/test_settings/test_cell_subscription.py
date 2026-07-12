"""bag.subscribe rides the cell event — one change primitive (ADR 0016).

``subscribe(cb)`` attaches one adapter per field cell, so EVERY writer —
descriptor set, registry write-through, edge drive into a shared cell —
notifies uniformly. The legacy channels (``_callbacks`` fan-out,
``_on_property_change``, ``on_change='method'`` string dispatch) are gone.
"""

from __future__ import annotations

import pytest

from haywire.core.settings.descriptor import setting
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.settings.settings_framework import FrameworkSettings
from haywire.core.settings.settings import Settings
from haywire.barn.builtin.types import FLOAT


class _SubSchema(FrameworkSettings, namespace="test.cellsub"):
    threshold = setting[FLOAT](1.5, label="Threshold")


KEY = "test.cellsub.threshold"


class _PlainBag(Settings):
    threshold = setting[FLOAT](0.5)


@pytest.fixture
def registry() -> SettingsRegistry:
    reg = SettingsRegistry()
    reg.register_schema(_SubSchema)
    return reg


def test_subscribe_hears_descriptor_writes():
    bag = _PlainBag()
    seen: list[tuple] = []
    bag.subscribe(lambda name, value, old: seen.append((name, value, old)))

    bag.threshold = 0.75

    assert seen == [("threshold", 0.75, 0.5)]


def test_subscribe_hears_raw_cell_writes():
    """An edge drive writes the shared cell directly — subscribers must hear it.
    (Previously silent: nothing called _on_property_change on that path.)"""
    bag = _PlainBag()
    desc = _PlainBag.__dict__["threshold"]
    seen: list[tuple] = []
    bag.subscribe(lambda name, value, old: seen.append((name, value, old)))

    bag._cell_for(desc).set_value(0.9)  # simulate edge drive into shared cell

    assert seen == [("threshold", 0.9, 0.5)]


def test_subscribe_hears_registry_write_through(registry):
    bag = _SubSchema()
    seen: list[tuple] = []
    bag.subscribe(lambda name, value, old: seen.append((name, value, old)))

    registry.set_global(KEY, 4.0, tier="workspace")

    assert ("threshold", 4.0, 1.5) in seen


def test_unsubscribe_stops_delivery():
    bag = _PlainBag()
    seen: list[tuple] = []
    cb = lambda name, value, old: seen.append((name, value, old))  # noqa: E731
    bag.subscribe(cb)
    bag.unsubscribe(cb)

    bag.threshold = 0.75

    assert seen == []


def test_cleanup_detaches_adapters_from_borrowed_registry_cell(registry):
    """A registry-owned cell outlives the bag — cleanup MUST detach adapters."""
    bag = _SubSchema()
    cell = registry.cell_for(KEY)
    before = cell.on_changed.handler_size
    bag.subscribe(lambda name, value, old: None)
    assert cell.on_changed.handler_size == before + 1

    bag.cleanup()

    assert cell.on_changed.handler_size == before


def test_reset_notifies_subscribers():
    bag = _PlainBag()
    bag.threshold = 0.75
    seen: list[tuple] = []
    bag.subscribe(lambda name, value, old: seen.append((name, value, old)))

    bag.reset("threshold")

    assert seen == [("threshold", 0.5, 0.75)]


def test_on_change_and_stored_params_are_gone():
    with pytest.raises(TypeError):
        setting[FLOAT](1.0, on_change="_cb")
    with pytest.raises(TypeError):
        setting[FLOAT](1.0, stored=False)


# ---------------------------------------------------------------------------
# subscribe_field — per-field subscription (one adapter on one cell)
# ---------------------------------------------------------------------------


class _TwoFieldBag(Settings):
    threshold = setting[FLOAT](0.5)
    gain = setting[FLOAT](1.0)


def test_subscribe_field_hears_only_its_field():
    bag = _TwoFieldBag()
    seen: list[tuple] = []
    bag.subscribe_field("threshold", lambda value, old: seen.append((value, old)))

    bag.gain = 2.0  # other field — silent
    bag.threshold = 0.75

    assert seen == [(0.75, 0.5)]


def test_subscribe_field_unknown_field_raises():
    bag = _TwoFieldBag()
    with pytest.raises(KeyError):
        bag.subscribe_field("no_such_field", lambda value, old: None)


def test_subscribe_field_is_idempotent_per_field():
    bag = _TwoFieldBag()
    seen: list[tuple] = []
    cb = lambda value, old: seen.append((value, old))  # noqa: E731
    bag.subscribe_field("threshold", cb)
    bag.subscribe_field("threshold", cb)  # duplicate — must not double-fire

    bag.threshold = 0.75

    assert seen == [(0.75, 0.5)]


def test_subscribe_field_same_callback_on_two_fields():
    bag = _TwoFieldBag()
    seen: list[tuple] = []
    cb = lambda value, old: seen.append((value, old))  # noqa: E731
    bag.subscribe_field("threshold", cb)
    bag.subscribe_field("gain", cb)

    bag.threshold = 0.75
    bag.gain = 2.0

    assert seen == [(0.75, 0.5), (2.0, 1.0)]


def test_unsubscribe_detaches_field_subscription():
    bag = _TwoFieldBag()
    seen: list[tuple] = []
    cb = lambda value, old: seen.append((value, old))  # noqa: E731
    bag.subscribe_field("threshold", cb)
    bag.unsubscribe(cb)

    bag.threshold = 0.75

    assert seen == []


def test_cleanup_detaches_field_adapters_from_registry_cell(registry):
    bag = _SubSchema()
    cell = registry.cell_for(KEY)
    before = cell.on_changed.handler_size
    bag.subscribe_field("threshold", lambda value, old: None)
    assert cell.on_changed.handler_size == before + 1

    bag.cleanup()

    assert cell.on_changed.handler_size == before
