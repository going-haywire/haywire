"""``hui.dropdown`` — the vertically-anchored, click-opened sibling of ``hui.flyout``.

What differs from a flyout is exactly three things, and each one is load-bearing
for content (as opposed to commands): it opens above or below (never beside,
and placed by two independent axes — ``align`` and ``direction``), on click, and
it never sets ``auto-close`` — measured in a browser, ``auto-close`` dismisses a
menu on any click inside it, so the first click into a field would shut the
panel. What is *shared* — the sibling group, cascade-close, the retroactive
greying of an empty body — is inherited from ``FlyoutIcon`` and pinned here too,
because sharing it is the reason the dropdown is a subclass rather than a copy.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.ui import elements as hui
from haywire.ui.elements.flyout import (
    DROPDOWN_ALIGNMENTS,
    DROPDOWN_DIRECTIONS,
    DROPDOWN_PROPS,
    DropdownIcon,
    FlyoutIcon,
    _leaves_drawn,
    dropdown_props,
    open_flyout_group,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


@pytest.mark.unit
@pytest.mark.anyio
async def test_dropdown_opens_below_and_never_auto_closes(user: User) -> None:
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.dropdown("tune", tooltip="Appearance") as drop:
                ui.label("content")
                _leaves_drawn.set(_leaves_drawn.get() + 1)
        captured["drop"] = drop

    await user.open("/")

    drop: DropdownIcon = captured["drop"]  # type: ignore[assignment]
    assert drop._menu._props.get("anchor") == "bottom start"
    assert drop._menu._props.get("self") == "top start"
    # auto-close closes the menu on ANY click inside it — fatal for fields.
    assert "auto-close" not in drop._menu._props
    assert DROPDOWN_PROPS == dropdown_props()  # left + down, what you get unasked


@pytest.mark.unit
@pytest.mark.anyio
@pytest.mark.parametrize("direction", sorted(DROPDOWN_DIRECTIONS))
@pytest.mark.parametrize("align", sorted(DROPDOWN_ALIGNMENTS))
async def test_align_and_direction_are_independent_axes(user: User, align: str, direction: str) -> None:
    """Every combination is composed from the two tables, so a placement can
    never exist in one direction and be missing in the other. ``align`` moves
    only the horizontal word of the Quasar point, ``direction`` only the
    vertical one."""
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.dropdown("tune", align=align, direction=direction) as drop:  # type: ignore[arg-type]
                ui.label("content")
                _leaves_drawn.set(_leaves_drawn.get() + 1)
        captured["drop"] = drop

    await user.open("/")

    drop: DropdownIcon = captured["drop"]  # type: ignore[assignment]
    anchor_v, self_v = DROPDOWN_DIRECTIONS[direction]
    anchor_h, self_h = DROPDOWN_ALIGNMENTS[align]
    assert drop._menu._props.get("anchor") == f"{anchor_v} {anchor_h}"
    assert drop._menu._props.get("self") == f"{self_v} {self_h}"
    assert "auto-close" not in drop._menu._props  # holds for every placement


@pytest.mark.unit
@pytest.mark.anyio
@pytest.mark.parametrize(
    ("align", "direction", "anchor", "self_point"),
    [
        ("left", "down", "bottom start", "top start"),
        ("right", "down", "bottom end", "top end"),
        ("center", "down", "bottom middle", "top middle"),
        ("left", "up", "top start", "bottom start"),
        ("right", "up", "top end", "bottom end"),
        ("center", "up", "top middle", "bottom middle"),
    ],
)
async def test_the_six_placements_spell_out_their_quasar_points(
    align: str, direction: str, anchor: str, self_point: str, user: User
) -> None:
    """The composed strings, written out once rather than derived, so a change
    to the tables has to be meant. "up" is the mirror of "down": the panel's
    BOTTOM edge meets the icon's TOP."""
    assert dropdown_props(align=align, direction=direction) == (  # type: ignore[arg-type]
        f'anchor="{anchor}" self="{self_point}"'
    )


@pytest.mark.unit
@pytest.mark.anyio
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"align": "middle"}, ("align='middle'", "left", "right", "center")),
        ({"direction": "downwards"}, ("direction='downwards'", "down", "up")),
    ],
)
async def test_an_unknown_placement_fails_at_construction(
    user: User, kwargs: dict, expected: tuple[str, ...]
) -> None:
    """An author-time typo, caught where it is written rather than showing up
    as a panel that opens in a surprising place."""
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            try:
                hui.dropdown("tune", **kwargs)
            except ValueError as exc:
                captured["error"] = str(exc)

    await user.open("/")

    message = str(captured.get("error", ""))
    for fragment in expected:
        assert fragment in message


@pytest.mark.unit
@pytest.mark.anyio
async def test_flyout_still_opens_beside_and_keeps_auto_close(user: User) -> None:
    """The dropdown's props must not have leaked onto the command flyout."""
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.flyout("more_horiz") as icon:
                ui.label("leaf")
                _leaves_drawn.set(_leaves_drawn.get() + 1)
        captured["icon"] = icon

    await user.open("/")

    icon: FlyoutIcon = captured["icon"]  # type: ignore[assignment]
    assert icon._menu._props.get("anchor") == "top end"
    assert "auto-close" in icon._menu._props


@pytest.mark.unit
@pytest.mark.anyio
async def test_dropdown_joins_the_sibling_group(user: User) -> None:
    """Opening one closes the others: a dropdown and a flyout in one toolbar are
    one open path, not two independent popups."""
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group() as siblings:
            with hui.dropdown("tune"):
                ui.label("content")
                _leaves_drawn.set(_leaves_drawn.get() + 1)
            with hui.flyout("more_horiz"):
                ui.label("leaf")
                _leaves_drawn.set(_leaves_drawn.get() + 1)
        captured["siblings"] = list(siblings)

    await user.open("/")

    assert len(captured["siblings"]) == 2  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.anyio
async def test_an_empty_dropdown_greys_its_anchor(user: User) -> None:
    """Inherited from FlyoutIcon: a body that drew nothing is not a control."""
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.dropdown("tune") as drop:
                pass
        captured["drop"] = drop

    await user.open("/")

    drop: DropdownIcon = captured["drop"]  # type: ignore[assignment]
    assert "hw-disabled" in drop._anchor._classes


@pytest.mark.unit
@pytest.mark.anyio
async def test_popups_spawned_inside_a_dropdown_are_lifted_above_it(user: User) -> None:
    """A select's option list and a colour picker are Quasar portals of their
    own at z-6000 — behind the dropdown that spawned them. They teleport to
    <body>, so no CSS rule can reach them; the dropdown stamps the lift on its
    whole body instead of asking content to opt in (content is usually built by
    the widget factory, where no caller could pass a flag)."""
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.dropdown("tune"):
                captured["select"] = ui.select(["a", "b"])
                captured["picker"] = ui.menu()  # what a colour picker is
                _leaves_drawn.set(_leaves_drawn.get() + 1)

    await user.open("/")

    select: ui.select = captured["select"]  # type: ignore[assignment]
    picker: ui.menu = captured["picker"]  # type: ignore[assignment]
    assert "z-index" in str(select._props.get("popup-content-style", ""))
    assert "z-index" in picker._style


@pytest.mark.unit
@pytest.mark.anyio
async def test_a_flyout_does_not_lift_nested_popups(user: User) -> None:
    """The lift is the dropdown's bargain only. A command flyout holds menu
    rows, and lifting there would raise a panel's dropdown above popups it
    should sit under (see hui.select_field's in_popup= reasoning)."""
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.flyout("more_horiz"):
                captured["select"] = ui.select(["a", "b"])
                _leaves_drawn.set(_leaves_drawn.get() + 1)

    await user.open("/")

    select: ui.select = captured["select"]  # type: ignore[assignment]
    assert "popup-content-style" not in select._props
