"""The account menu — a panel-driven context menu, so access filtering is free."""

from unittest.mock import MagicMock

from haywire.barn.builtin.focuses import AccountFocus
from haywire.ui.app.account_menu import AccountMenuProvider


def test_account_focus_id_is_stable():
    assert AccountFocus.id == "account"


def test_account_focus_is_always_available():
    assert AccountFocus.available(MagicMock()) is True


def test_open_queries_panels_for_the_account_focus(monkeypatch):
    provider = AccountMenuProvider(context=MagicMock(), session=MagicMock(), panel_registry=MagicMock())
    seen = {}

    def _open_menu(action, focus, pos, on_close=None):
        seen["action"] = action
        seen["focus"] = focus
        seen["pos"] = pos

    monkeypatch.setattr(provider, "_open_menu", _open_menu)
    provider.open((10.0, 20.0))

    assert seen["focus"] is AccountFocus
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
