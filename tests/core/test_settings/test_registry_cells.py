"""Registry-owned cells — one live DataField per persistent definition (ADR 0016).

The registry, which already owns the tier values, also owns their single live
cell: ``cell_for(key)`` lazily creates it seeded via ``resolve(key)``, every
tier mutation writes the new effective value through to it, and the cell dies
with its definition (hot-reload unregister). Instances and panels borrow this
cell — "one cell, N views".
"""

from __future__ import annotations

import pytest

from haywire.core.settings.descriptor import setting
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.settings.settings_framework import FrameworkSettings
from haywire.barn.builtin.types import FLOAT


class _CellSchema(FrameworkSettings, namespace="test.regcell"):
    threshold = setting[FLOAT](1.5, label="Threshold")


@pytest.fixture
def registry() -> SettingsRegistry:
    reg = SettingsRegistry()
    reg.register_schema(_CellSchema)
    return reg


KEY = "test.regcell.threshold"


def test_cell_for_seeds_from_resolve_and_stamps_id(registry):
    cell = registry.cell_for(KEY)
    assert cell.get_value() == 1.5  # no tier set -> definition default
    assert cell.field_id == KEY


def test_cell_for_is_cached(registry):
    assert registry.cell_for(KEY) is registry.cell_for(KEY)


def test_cell_for_unknown_key_raises(registry):
    with pytest.raises(KeyError):
        registry.cell_for("no.such.key")


def test_cell_for_seeds_from_set_tier(registry):
    registry.set_global(KEY, 3.25, tier="workspace")
    assert registry.cell_for(KEY).get_value() == 3.25


def test_set_global_writes_through_to_cell(registry):
    cell = registry.cell_for(KEY)
    seen = []
    cell.on_changed.append(seen.append)

    registry.set_global(KEY, 2.5, tier="workspace")

    assert cell.get_value() == 2.5
    assert seen[-1].value == 2.5
    assert seen[-1].old == 1.5


def test_reset_global_writes_effective_back_to_cell(registry):
    registry.set_global(KEY, 9.0, tier="global")
    registry.set_global(KEY, 2.5, tier="workspace")
    cell = registry.cell_for(KEY)
    assert cell.get_value() == 2.5

    registry.reset_global(KEY, tier="workspace")
    assert cell.get_value() == 9.0  # falls to global tier

    registry.reset_global(KEY, tier="global")
    assert cell.get_value() == 1.5  # falls to definition default


def test_cell_dropped_when_definition_unregisters(registry):
    cell = registry.cell_for(KEY)
    assert cell is not None

    registry._unregister_schema_fields(_CellSchema)

    with pytest.raises(KeyError):
        registry.cell_for(KEY)
