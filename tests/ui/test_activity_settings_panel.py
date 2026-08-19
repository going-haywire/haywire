"""ActivitySettingsPanel — Application-focus panel rendering ActivitySettings."""

import pytest

pytestmark = pytest.mark.unit


def test_panel_is_registered_under_app_focus():
    from haybale_studio.panels.properties.setting.app import ActivitySettingsPanel
    from haywire.barn.builtin.focuses import AppFocus

    assert ActivitySettingsPanel.class_identity.focus is AppFocus


def test_panel_label_and_icon_match_the_rest_of_the_feature():
    """Icon matches ActivityEditor/OpenActivityPanel's smart_toy, not a placeholder."""
    from haybale_studio.panels.properties.setting.app import ActivitySettingsPanel

    identity = ActivitySettingsPanel.class_identity
    assert identity.label == "Activity"
    assert identity.icon == "smart_toy"


def test_draw_renders_the_activity_settings_schema(monkeypatch):
    """Drives the real draw(), so a wrong schema class is caught here, not in the browser."""
    from unittest.mock import MagicMock

    from haybale_studio.panels.properties.setting import app as app_mod

    calls = []
    monkeypatch.setattr(app_mod, "render_schema", lambda schema_cls, registry: calls.append(schema_cls))

    panel = app_mod.ActivitySettingsPanel.__new__(app_mod.ActivitySettingsPanel)
    ctx = MagicMock()
    panel.draw(ctx, MagicMock())

    assert calls == [app_mod.ActivitySettings]
