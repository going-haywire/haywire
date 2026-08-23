"""Proof for the render-then-discard mechanism ADR-0029 relies on.

A context menu decides whether to open by *rendering its whole tree* and keeping
the popup only if a leaf panel drew (ADR-0029, Routing). That rests on two
framework properties that were previously asserted from reading code rather than
running it, and ``Popup.delete`` had no coverage at all:

1. A ``Popup`` built but never opened is not shown to the user.
2. ``delete()`` reclaims the popup *and its whole subtree*, including any
   ``ui.timer`` a discarded panel created during its ``draw()``.

If either regresses, a right-click that should show nothing would leave a visible
empty popup, or would leak a timer per discarded menu. Both fail far from here.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from nicegui import ui
from nicegui.client import Client
from nicegui.element import Element
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.ui.components.popup import Popup


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on the asyncio backend."""
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    """A NiceGUI ``User`` simulator without the user_plugin's main_file requirement."""
    async with user_simulation() as u:
        yield u


@pytest.mark.unit
@pytest.mark.anyio
async def test_unopened_popup_is_not_shown(user: User) -> None:
    """A built-but-never-opened Popup stays hidden.

    ``popup.vue`` gates its card on ``v-show="visible"``, with ``visible: false``
    initially and only ``startVisible`` or ``open()`` flipping it. Python passes
    ``start-visible: False`` at construction, so the render-then-discard sequence
    can build a popup, fill it, and throw it away with nothing on screen.
    """
    captured: dict[str, Popup] = {}

    @ui.page("/")
    def page() -> None:
        popup = Popup(position_x=10, position_y=20)
        with popup:
            ui.label("panels would render here")
        captured["popup"] = popup

    await user.open("/")

    popup = captured["popup"]
    assert popup._props["start-visible"] is False
    assert popup.is_open is False

    # The flag is not vacuously false — opening flips it.
    popup.open()
    assert popup.is_open is True


@pytest.mark.unit
@pytest.mark.anyio
async def test_delete_reclaims_the_whole_subtree(user: User) -> None:
    """Discarding a popup removes every element rendered into it."""
    popups: dict[str, Popup] = {}
    elements: dict[str, Element] = {}
    clients: dict[str, Client] = {}

    @ui.page("/")
    def page() -> None:
        popup = Popup(position_x=0, position_y=0)
        with popup:
            with ui.column() as nested:
                leaf = ui.label("a panel drew this")
        popups["popup"] = popup
        elements.update(nested=nested, leaf=leaf)
        clients["client"] = ui.context.client

    await user.open("/")

    popup = popups["popup"]
    client = clients["client"]
    ids = [popup.id, elements["nested"].id, elements["leaf"].id]
    assert all(i in client.elements for i in ids)

    popup.delete()

    assert not any(i in client.elements for i in ids), "popup subtree survived delete()"
    assert elements["leaf"].is_deleted


@pytest.mark.unit
@pytest.mark.anyio
async def test_delete_cancels_a_timer_created_during_draw(user: User) -> None:
    """A ui.timer created inside the discarded tree is cancelled, not leaked.

    ``Element.delete()`` → ``remove_elements`` → ``_handle_delete()`` per
    descendant, and ``Timer._handle_delete`` cancels itself. This is what makes
    running ``draw()`` for a menu nobody sees affordable: a panel that starts a
    timer while drawing does not outlive the popup it drew into.

    A timer deliberately re-parented to a stable element would still survive —
    that is a panel-authoring problem, not a framework one.
    """
    popups: dict[str, Popup] = {}
    timers: dict[str, ui.timer] = {}

    @ui.page("/")
    def page() -> None:
        popup = Popup(position_x=0, position_y=0)
        with popup:
            timers["timer"] = ui.timer(60.0, lambda: None)
        popups["popup"] = popup

    await user.open("/")

    timer = timers["timer"]
    assert timer._is_canceled is False

    popups["popup"].delete()

    assert timer._is_canceled is True, "timer outlived the popup it was created in"
