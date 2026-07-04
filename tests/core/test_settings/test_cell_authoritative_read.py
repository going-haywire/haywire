"""Cell-authoritative reads — setting.__get__ is a pure cell read (ADR 0016).

The resolution chain runs at write/seed time only; a read never walks it.
A wired persistent field borrows THE registry-owned cell (one cell, N views);
everything else reads its instance cell.
"""

from __future__ import annotations

import pytest

from haywire.core.settings.descriptor import setting
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.settings.schema import FrameworkSettings
from haywire.core.settings.settings import Settings
from haywire.barn.builtin.types import FLOAT


class _ReadSchema(FrameworkSettings, namespace="test.cellread"):
    threshold = setting[FLOAT](1.5, label="Threshold")


KEY = "test.cellread.threshold"


@pytest.fixture
def registry() -> SettingsRegistry:
    reg = SettingsRegistry()
    reg.register_schema(_ReadSchema)
    return reg


def test_wired_instance_borrows_registry_cell(registry):
    bag = _ReadSchema()
    desc = _ReadSchema.__dict__["threshold"]
    assert bag._cell_for(desc) is registry.cell_for(KEY)


def test_wired_read_is_live_through_registry_cell(registry):
    bag = _ReadSchema()
    assert bag.threshold == 1.5
    registry.set_global(KEY, 4.25, tier="workspace")
    assert bag.threshold == 4.25
    registry.reset_global(KEY, tier="workspace")
    assert bag.threshold == 1.5


def test_read_never_walks_the_resolution_chain(registry, monkeypatch):
    """__get__ must not call _resolve — the chain runs at write/seed time only."""
    bag = _ReadSchema()
    registry.set_global(KEY, 2.5, tier="workspace")

    def _boom(*a, **kw):  # pragma: no cover - failure path
        raise AssertionError("read walked the resolution chain")

    monkeypatch.setattr(Settings, "_resolve", _boom)
    assert bag.threshold == 2.5


def test_unwired_instance_keeps_instance_cell():
    """No registry (test-fixture/simple mode): instance-owned cell, local writes work."""

    class _Plain(Settings):
        threshold = setting[FLOAT](0.5)

    bag = _Plain()
    assert bag.threshold == 0.5
    bag.threshold = 0.75
    assert bag.threshold == 0.75
