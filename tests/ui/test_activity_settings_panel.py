"""ActivitySettingsPanel — Application-focus panel rendering ActivitySettings."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_panel_is_registered_under_app_focus():
    from haybale_studio.panels.properties.setting.app import ActivitySettingsPanel
    from haywire.barn.builtin.surfaces import AppSettingsSurface

    assert ActivitySettingsPanel.class_identity.surface is AppSettingsSurface


def test_draw_renders_the_activity_settings_schema(monkeypatch):
    """Drives the real draw(), so a wrong schema class is caught here, not in the browser."""
    from unittest.mock import MagicMock

    from haybale_studio.panels.properties.setting import app as app_mod

    calls = []
    monkeypatch.setattr(app_mod, "render_schema", lambda ctx, schema_cls, registry: calls.append(schema_cls))

    panel = app_mod.ActivitySettingsPanel.__new__(app_mod.ActivitySettingsPanel)
    ctx = MagicMock()
    panel.draw(ctx, MagicMock())

    assert calls == [app_mod.ActivitySettings]
