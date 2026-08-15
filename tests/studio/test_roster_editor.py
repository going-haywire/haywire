"""RosterEditor and the account menu panels."""

from haywire.core.access import AccessTier


def test_roster_editor_requires_admin():
    from haybale_studio.editors.roster_editor import RosterEditor

    assert RosterEditor.class_identity.access is AccessTier.ADMIN


def test_logout_panel_is_visible_to_everyone():
    from haybale_studio.panels.account.account import LogoutPanel

    assert LogoutPanel.class_identity.access is AccessTier.VIEW


def test_open_roster_panel_requires_admin():
    from haybale_studio.panels.account.account import OpenRosterPanel

    assert OpenRosterPanel.class_identity.access is AccessTier.ADMIN


def test_rotate_secret_panel_requires_admin():
    from haybale_studio.panels.account.account import RotateSecretPanel

    assert RotateSecretPanel.class_identity.access is AccessTier.ADMIN


def test_account_panels_target_the_account_focus():
    from haywire.barn.builtin.focuses import AccountFocus
    from haybale_studio.panels.account.account import LogoutPanel, OpenRosterPanel

    assert LogoutPanel.class_identity.focus is AccountFocus
    assert OpenRosterPanel.class_identity.focus is AccountFocus


def test_logout_panel_hidden_when_authentication_is_off():
    """With no principal there is nothing to log out of — the menu stays empty."""
    from unittest.mock import MagicMock

    from haybale_studio.panels.account.account import LogoutPanel

    ctx = MagicMock()
    ctx.principal = None
    assert LogoutPanel.poll(ctx) is False

    ctx.principal = "alice"
    assert LogoutPanel.poll(ctx) is True
