"""HaystackSettingsPanel — single-control panel for the autosave setting."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


def test_panel_is_a_basepanel():
    from haybale_haystack.panels.haystack_settings_panel import HaystackSettingsPanel
    from haywire.ui.panel import BasePanel

    assert issubclass(HaystackSettingsPanel, BasePanel)


def test_panel_pinned_to_app_focus_via_decorator():
    """The @panel decorator stamps focus/action/label onto the class."""
    from haybale_haystack.panels.haystack_settings_panel import HaystackSettingsPanel
    from haybale_studio.focuses import AppFocus
    from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions

    ident = HaystackSettingsPanel.class_identity
    assert ident.focus is AppFocus
    assert ident.action is PropertiesEditorActions
    assert ident.label == "Haystack"


def test_panel_poll_returns_true():
    """AppFocus is always available, so the panel always polls true."""
    from haybale_haystack.panels.haystack_settings_panel import HaystackSettingsPanel

    ctx = MagicMock()
    assert HaystackSettingsPanel.poll(ctx) is True


def test_draw_delegates_to_render_schema():
    """draw() must hand HaystackSettings to render_schema with the registry from
    the session context. This is the panel's whole contract — render_schema
    handles widget construction and the registry-backed setter."""
    from haybale_haystack.panels.haystack_settings_panel import HaystackSettingsPanel
    from haybale_haystack.settings.haystack_settings import HaystackSettings

    panel_inst = HaystackSettingsPanel()
    ctx = MagicMock()
    fake_registry = MagicMock()
    ctx.app.library_service.get_settings_registry.return_value = fake_registry

    with patch("haybale_haystack.panels.haystack_settings_panel.render_schema") as render_mock:
        panel_inst.draw(ctx, MagicMock(), MagicMock())

    render_mock.assert_called_once_with(HaystackSettings, fake_registry)
