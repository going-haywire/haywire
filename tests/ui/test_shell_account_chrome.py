"""Account chrome — the footer region, the identity label, the presence row."""

from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from nicegui import Client

from haywire.core.access import AccessTier


def _noop_page() -> None:  # registration target for a headless Client
    pass


def test_icon_slot_has_a_footer_hook():
    from haywire.ui.app.icon_slot import IconSlot

    assert hasattr(IconSlot, "set_footer")


def test_footer_renderer_is_invoked_during_bar_render(monkeypatch):
    from nicegui import ui

    from haywire.ui.app.icon_slot import IconSlot

    session = MagicMock()
    session.context.can_access.return_value = True
    slot = IconSlot(session=session, name="action", registry=MagicMock())

    called = []
    slot.set_footer(lambda: called.append(True))
    slot._bindings = []

    client = Client(cast(Any, _noop_page), request=None)
    with client, ui.column():
        slot._render_bar_contents()

    assert called == [True]


def test_identity_text_names_the_principal_and_tier():
    from haywire.ui.app.shell import identity_text

    assert identity_text("alice", AccessTier.ADMIN) == "alice · admin"


def test_identity_text_is_empty_when_auth_is_off():
    from haywire.ui.app.shell import identity_text

    assert identity_text(None, AccessTier.ADMIN) == ""


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(5, "just now"), (65, "1m ago"), (3700, "1h ago")],
)
def test_last_seen_text(seconds, expected):
    from haywire.ui.app.shell import last_seen_text

    assert last_seen_text(seconds) == expected
