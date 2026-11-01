"""ImageSettingsPanel: Barns panel rendering ImageSettings."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


def test_panel_is_registered_under_barns():
    from haybale_image.panels.image_settings_panel import ImageSettingsPanel
    from haywire.barn.builtin.surfaces import Barns

    identity = ImageSettingsPanel.class_identity
    assert identity.surface is Barns
    assert identity.label == "Image"


def test_draw_renders_image_settings_schema(monkeypatch):
    from haybale_image.panels import image_settings_panel as mod

    calls = []
    monkeypatch.setattr(mod, "render_schema", lambda ctx, schema_cls, registry: calls.append(schema_cls))
    panel = mod.ImageSettingsPanel.__new__(mod.ImageSettingsPanel)
    panel.draw(MagicMock(), MagicMock())
    assert calls == [mod.ImageSettings]


def test_schema_has_jpeg_quality_field():
    from haybale_image.settings.image_settings import ImageSettings

    assert ImageSettings.jpeg_quality._label == "JPEG quality"
