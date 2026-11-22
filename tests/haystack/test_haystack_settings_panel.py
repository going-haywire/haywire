"""FlowMeterSettings and the haystack library's Barns panel."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from haywire.ui import elements as hui

pytestmark = pytest.mark.unit


def test_flow_meters_are_on_by_default():
    from haybale_haystack.settings.flow_meter_settings import FlowMeterSettings

    assert FlowMeterSettings().show is True


def test_the_bookkeeping_settings_stay_out_of_the_schema():
    from haybale_haystack.settings.flow_meter_settings import FlowMeterSettings

    assert list(FlowMeterSettings._settings_descriptors()) == ["show"]


def test_panel_is_registered_under_barns():
    from haybale_haystack.panels.haystack_settings_panel import HaystackSettingsPanel
    from haywire.barn.builtin.surfaces import BarnsSurface

    identity = HaystackSettingsPanel.class_identity
    assert identity.surface is BarnsSurface
    assert identity.icon == hui.icon.haystack, "and carries the library's icon"


def test_draw_renders_the_flow_meter_schema(monkeypatch):
    from haybale_haystack.panels import haystack_settings_panel as mod

    calls = []
    monkeypatch.setattr(mod, "render_schema", lambda ctx, schema_cls, registry: calls.append(schema_cls))
    panel = mod.HaystackSettingsPanel.__new__(mod.HaystackSettingsPanel)
    panel.draw(MagicMock(), MagicMock())
    assert calls == [mod.FlowMeterSettings]
