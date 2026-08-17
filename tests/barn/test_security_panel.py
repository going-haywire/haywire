"""The Security panel reports the in-force document, and writes nothing."""

from __future__ import annotations

import inspect

from haywire.core.access import AccessTier


def test_panel_is_admin_gated():
    from haybale_studio.panels.properties.setting.app import SecurityPanel

    assert SecurityPanel.class_identity.access is AccessTier.ADMIN


def test_network_settings_panel_is_gone():
    """The writable panel must not survive alongside the read-only one."""
    import haybale_studio.panels.properties.setting.app as module

    assert not hasattr(module, "NetworkSettingsPanel")


def test_panel_renders_no_security_schema():
    """render_schema on NetworkSettings would put 'port' in front of an admin —
    fine — but any other bag here would be a writable security control."""
    from haybale_studio.panels.properties.setting.app import SecurityPanel

    source = inspect.getsource(SecurityPanel)
    assert "FarmhandSettings" not in source
    assert "render_schema(NetworkSettings" in source


def test_panel_reads_the_in_force_document_not_disk():
    """A disk read here would report a change the running studio has not applied."""
    from haybale_studio.panels.properties.setting.app import SecurityPanel

    source = inspect.getsource(SecurityPanel)
    assert "security_document" in source
    assert "load_document" not in source
