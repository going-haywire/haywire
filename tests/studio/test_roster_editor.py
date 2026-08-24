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
    from haywire.barn.builtin.surfaces import AccountMenu
    from haybale_studio.panels.account.account import LogoutPanel, OpenRosterPanel

    assert LogoutPanel.class_identity.surface is AccountMenu
    assert OpenRosterPanel.class_identity.surface is AccountMenu


def test_logout_panel_hidden_when_authentication_is_off():
    """With no principal there is nothing to log out of — the menu stays empty."""
    from unittest.mock import MagicMock

    from haybale_studio.panels.account.account import LogoutPanel

    ctx = MagicMock()
    ctx.principal = None
    assert LogoutPanel.poll(ctx) is False

    ctx.principal = "alice"
    assert LogoutPanel.poll(ctx) is True


def test_set_tier_refuses_to_change_the_acting_principals_own_tier():
    """A logged-in admin must not be able to demote themselves from the roster UI."""
    from unittest.mock import MagicMock, patch

    from haybale_studio.editors.roster_editor import RosterEditor

    editor = RosterEditor(MagicMock())
    with (
        patch("haybale_studio.editors.roster_editor.set_tier") as mock_set_tier,
        patch("haybale_studio.editors.roster_editor.ui.notify"),
    ):
        editor._set_tier("alice", "view", acting_as="alice")

    mock_set_tier.assert_not_called()


def test_set_tier_allows_changing_another_principals_tier():
    from unittest.mock import MagicMock, patch

    from haywire.core.access import AccessTier
    from haybale_studio.editors.roster_editor import RosterEditor

    editor = RosterEditor(MagicMock())
    with (
        patch("haybale_studio.editors.roster_editor.set_tier") as mock_set_tier,
        patch("haybale_studio.editors.roster_editor.ui.notify"),
    ):
        editor._set_tier("bob", "view", acting_as="alice")

    mock_set_tier.assert_called_once_with("bob", AccessTier.VIEW)
