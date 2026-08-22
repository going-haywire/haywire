"""Shared fixtures for the skin render tests."""

from __future__ import annotations

from typing import Any, cast

import pytest

# Lazily-captured persistent NiceGUI default client (see nicegui_slot_context).
_CLIENT: list = []


def _noop_page() -> None:  # registration target for a headless Client
    pass


@pytest.fixture
def nicegui_slot_context():
    """Keep a valid NiceGUI default slot active for the test body.

    The autouse ``_reset_nicegui_globals`` clears ``Slot.stacks`` after every
    test, so any ``ui.element`` built without an active slot raises "slot stack
    is empty" as soon as no earlier test in the run happens to have left one
    open. Materializing goes through ``Client(...)`` (which passes ``_client=``
    explicitly to its root ``Element``) rather than a bare ``ui.element(...)``,
    which would read ``context.client`` off whatever slot is already on the
    stack and so only work by accident of ordering.

    Mirrors the fixture of the same name in ``tests/ui/widget/conftest.py``;
    kept local because conftest fixtures do not cross sibling directories.
    """
    from nicegui import Client

    if not _CLIENT:
        _CLIENT.append(Client(cast(Any, _noop_page), request=None))
    with _CLIENT[0]:
        yield
