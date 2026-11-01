"""ModelsSettingsPanel: Barns panel rendering ModelsSettings."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


def test_panel_is_registered_under_barns():
    from haybale_models.panels.models_settings_panel import ModelsSettingsPanel
    from haywire.barn.builtin.surfaces import Barns

    identity = ModelsSettingsPanel.class_identity
    assert identity.surface is Barns
    assert identity.label == "Models"


def test_draw_renders_models_settings_schema(monkeypatch):
    from haybale_models.panels import models_settings_panel as mod

    calls = []
    monkeypatch.setattr(mod, "render_schema", lambda ctx, schema_cls, registry: calls.append(schema_cls))
    panel = mod.ModelsSettingsPanel.__new__(mod.ModelsSettingsPanel)
    panel.draw(MagicMock(), MagicMock())
    assert calls == [mod.ModelsSettings]


def test_schema_has_parallel_downloads_field():
    from haybale_models.settings.models_settings import ModelsSettings

    assert ModelsSettings.max_parallel_downloads._label == "Parallel downloads"
