"""The account menu — a panel-driven context menu, so access filtering is free."""

from unittest.mock import MagicMock

from haywire.barn.builtin.surfaces import AccountActions, AccountMenu
from haywire.ui.app.account_menu import AccountMenuProvider


def test_account_menu_id_is_stable():
    assert AccountMenu.id == "account"


def test_account_menu_always_applies():
    """Its entries are access-filtered by the shared panel gate, and a menu
    whose tree draws nothing does not open — so a principal with no entries
    needs no special case here."""
    assert AccountMenu.poll(MagicMock()) is True


def test_account_menu_declares_no_presentation():
    """A menu surface has no chrome of its own, so the properties strip does
    not list it even though it is a root."""
    assert AccountMenu.presentation is None


def test_the_provider_satisfies_the_surface_contract():
    """The name collision is deliberate: AccountMenu is the surface,
    AccountMenuProvider is the host that opens it."""
    assert AccountMenu.provides is AccountActions
    provider = AccountMenuProvider(context=MagicMock(), session=MagicMock(), panel_registry=MagicMock())
    assert isinstance(provider, AccountActions)


def test_open_opens_the_account_menu_surface(monkeypatch):
    provider = AccountMenuProvider(context=MagicMock(), session=MagicMock(), panel_registry=MagicMock())
    seen = {}

    def _open_menu(surface, pos, on_close=None):
        seen["surface"] = surface
        seen["pos"] = pos

    monkeypatch.setattr(provider, "_open_menu", _open_menu)
    provider.open((10.0, 20.0))

    assert seen["surface"] is AccountMenu
    assert seen["pos"] == (10.0, 20.0)


def test_logout_navigates_the_client_to_the_logout_route():
    provider = AccountMenuProvider(context=MagicMock(), session=MagicMock(), panel_registry=MagicMock())
    provider._open_popup = MagicMock()
    ran = []
    provider._run_js = lambda script: ran.append(script)  # type: ignore[method-assign]

    provider.logout()

    assert "/logout" in ran[0]
    provider._open_popup.close.assert_called_once()


def test_reveal_publishes_a_reveal_signal_and_closes():
    session = MagicMock()
    provider = AccountMenuProvider(context=MagicMock(), session=session, panel_registry=MagicMock())
    provider._open_popup = MagicMock()

    marker = type("E", (), {})
    provider.reveal(marker, None, "Roster")

    assert session.publish.called
    provider._open_popup.close.assert_called_once()
