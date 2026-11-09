"""FlowMeterSettings and its Barns panel."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


def test_flow_meters_are_on_by_default():
    from haybale_haystack.settings.flow_meter_settings import FlowMeterSettings

    assert FlowMeterSettings().show is True


def test_the_setting_has_a_label_a_user_can_find():
    from haybale_haystack.settings.flow_meter_settings import FlowMeterSettings

    assert FlowMeterSettings.show._label == "Show flow meters"


def test_the_bookkeeping_settings_stay_out_of_the_schema():
    from haybale_haystack.settings.flow_meter_settings import FlowMeterSettings

    assert list(FlowMeterSettings._settings_descriptors()) == ["show"]


def test_panel_is_registered_under_barns():
    from haywire.barn.builtin.surfaces import Barns

    from haybale_haystack.panels.flow_meter_settings_panel import FlowMeterSettingsPanel

    identity = FlowMeterSettingsPanel.class_identity
    assert identity.surface is Barns
    assert identity.label == "Flow meters"


def test_draw_renders_the_flow_meter_schema(monkeypatch):
    from haybale_haystack.panels import flow_meter_settings_panel as mod

    calls = []
    monkeypatch.setattr(mod, "render_schema", lambda ctx, schema_cls, registry: calls.append(schema_cls))
    panel = mod.FlowMeterSettingsPanel.__new__(mod.FlowMeterSettingsPanel)
    panel.draw(MagicMock(), MagicMock())
    assert calls == [mod.FlowMeterSettings]
