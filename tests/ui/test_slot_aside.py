"""Tests for AsideSlot — the ASIDE column, opened and closed from the top bar.

The column is closed by default, hides with its tab bar, opens on a reveal, and
while closed shows each editor's tab interior next to its top-bar toggle.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import Any, cast

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.core.signals import Reveal
from haywire.ui.app.aside_slot import AsideSlot
from haywire.ui.app.shell import AppShell
from haywire.ui.editor.identity import OpenBehavior, SlotName

_ALLOW_ALL_SESSION = SimpleNamespace(context=SimpleNamespace(can_access=lambda required: True))


class _FakeRegistry:
    """The slice of EditorRegistry a slot and its wrappers touch."""

    def __init__(self, by_slot: dict | None = None) -> None:
        self._by_slot = by_slot or {}

    def add_batch_event_subscriber(self, _cb) -> None:
        pass

    def remove_batch_event_subscriber(self, _cb) -> None:
        pass

    def add_event_subscriber(self, _key, _cb) -> None:
        pass

    def remove_event_subscriber(self, _key, _cb) -> None:
        pass

    def get_by_default_slot(self, slot_name) -> dict:
        return self._by_slot.get(slot_name, {})

    def get_by_key(self, _key):
        return None


def _editor_cls(key: str, opens: OpenBehavior = OpenBehavior.ON_CONTEXT) -> type:
    return type(
        f"_E_{key}",
        (),
        {
            "class_identity": SimpleNamespace(
                registry_key=key, label=key, icon="extension", opens=opens, default_slot=SlotName.ASIDE
            )
        },
    )


def _aside(*, visible: bool = False, size: int = 360) -> AsideSlot:
    return AsideSlot(
        session=cast(Any, _ALLOW_ALL_SESSION),
        name=SlotName.ASIDE,
        registry=cast(Any, _FakeRegistry()),
        bar_place="top",
        visible=visible,
        size=size,
    )


def _buttons(box: ui.element) -> list[ui.button]:
    return [e for e in box.descendants() if isinstance(e, ui.button)]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


async def _render(user: User, slot: AsideSlot, keys: tuple[str, ...] = ()) -> ui.row:
    """Render ``slot`` with one binding per key, and its toggle; return the toggle's box."""
    captured: dict[str, ui.row] = {}

    @ui.page("/")
    def page() -> None:
        for key in keys:
            slot.add_binding(editor_key=key, editor_cls=cast(Any, _editor_cls(key)))
        if slot.bindings:
            slot._active = slot.bindings[0]
        with ui.row() as row:
            slot.render(row)
        with ui.row() as toggle_box:
            slot.render_toggle(toggle_box)
        captured["toggle_box"] = toggle_box

    await user.open("/")
    return captured["toggle_box"]


@pytest.mark.unit
@pytest.mark.anyio
async def test_a_closed_aside_hides_its_column_and_shows_an_unlit_toggle(user: User) -> None:
    slot = _aside()
    box = await _render(user, slot)

    assert slot._column is not None
    assert slot._column.visible is False
    assert slot._column.props["id"] == "hw-slot-aside"
    assert slot._column.style["width"] == "360px"
    (toggle,) = _buttons(box)
    assert "hw-shell-toolbar-btn-active" not in toggle.classes
    # The keymap and the active-slot CSS find a slot by this stamp.
    assert any(e.props.get("data-hw-slot") == "aside" for e in slot._column.descendants())


@pytest.mark.unit
@pytest.mark.anyio
async def test_the_toggle_opens_and_closes_the_whole_column(user: User) -> None:
    slot = _aside()
    seen: list[bool] = []
    slot._on_visibility_change = seen.append
    box = await _render(user, slot)

    user.find(ui.button).click()
    assert slot.visible is True
    assert slot._column is not None
    assert slot._column.visible is True
    (toggle,) = _buttons(box)
    assert "hw-shell-toolbar-btn-active" in toggle.classes

    slot.toggle()
    assert slot.visible is False
    assert slot._column.visible is False
    assert seen == [True, False]


@pytest.mark.unit
@pytest.mark.anyio
async def test_while_closed_each_editor_sits_next_to_the_toggle_and_opens_on_click(user: User) -> None:
    slot = _aside()
    box = await _render(user, slot, keys=("a", "b"))

    _tab_a, tab_b, toggle = _buttons(box)
    assert "hw-shell-toolbar-btn-active" not in toggle.classes

    tab_b.mark("aside-tab-b")
    user.find(marker="aside-tab-b").click()

    assert slot.visible is True
    assert slot.active_binding_id == "b"
    assert len(_buttons(box)) == 1  # open: the toggle alone


@pytest.mark.unit
@pytest.mark.anyio
async def test_an_editor_repainting_its_tab_repaints_it_next_to_the_closed_toggle(user: User) -> None:
    slot = _aside()
    box = await _render(user, slot, keys=("a",))
    before = _buttons(box)[0]

    slot.bindings[0].refresh_tab_bar()

    after = _buttons(box)[0]
    assert after is not before
    assert len(_buttons(box)) == 2


@pytest.mark.unit
@pytest.mark.anyio
async def test_a_reveal_opens_a_closed_aside(user: User) -> None:
    slot = _aside()
    await _render(user, slot)

    changed = slot.reveal(Reveal(editor=cast(Any, _editor_cls("c")), binding_id=None))

    assert changed is True
    assert slot.visible is True
    assert slot.active_binding_id == "c"


@pytest.mark.unit
def test_open_state_and_width_round_trip_through_the_snapshot() -> None:
    slot = _aside(visible=True, size=420)
    snapshot = slot.to_snapshot()
    assert snapshot["visible"] is True
    assert snapshot["size"] == 420

    restored = _aside()
    restored.populate_from_snapshot(snapshot)
    assert restored.visible is True
    assert restored._size == 420


@pytest.mark.unit
def test_the_shell_builds_aside_closed_and_360px_wide_without_a_snapshot_entry() -> None:
    session = SimpleNamespace(
        workspace_manager=SimpleNamespace(snapshot={}), context=_ALLOW_ALL_SESSION.context
    )
    shell = AppShell(session=cast(Any, session), editor_registry=cast(Any, _FakeRegistry()))

    slot = shell._build_managed_slot(SlotName.ASIDE, bar_place="top")

    assert isinstance(slot, AsideSlot)
    assert slot.visible is False
    assert slot._size == 360
    assert shell._managed_slots[SlotName.ASIDE] is slot
