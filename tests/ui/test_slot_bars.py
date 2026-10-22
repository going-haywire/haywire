"""``hui.slot_header`` and ``hui.editor_toolbar`` — one look for every slot bar and editor toolbar.

A slot bar is the top strip of a slot: the shell's tab bar in EDIT and INFO, an
editor's ``slot_header`` in ACTION and CONTEXT. An editor toolbar is the second
row an editor draws under the tab bar. Each kind has one height, background and
separator, and no editor draws a bare Tailwind border, whose colour is the text
colour.
"""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.ui import elements as hui

_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


async def _render(user: User, build) -> ui.row:
    captured: dict[str, ui.row] = {}

    @ui.page("/")
    def page() -> None:
        with build() as row:
            captured["row"] = row

    await user.open("/")
    return captured["row"]


@pytest.mark.unit
@pytest.mark.anyio
async def test_a_slot_header_has_the_slot_bar_look(user: User) -> None:
    row = await _render(user, lambda: hui.slot_header("Single", icon="folder"))

    assert "hw-slot-header" in row.classes
    assert row.style["min-height"] == "36px"
    assert row.style["background"] == "var(--hw-bg-surface)"
    assert row.style["border-bottom"] == "1px solid var(--hw-border)"


@pytest.mark.unit
@pytest.mark.anyio
async def test_a_slot_header_without_a_title_draws_no_label(user: User) -> None:
    row = await _render(user, hui.slot_header)

    assert not [e for e in row.descendants() if isinstance(e, ui.label)]


@pytest.mark.unit
@pytest.mark.anyio
async def test_a_slot_header_without_a_title_still_draws_its_icon_and_dirty_dot(user: User) -> None:
    row = await _render(user, lambda: hui.slot_header(icon="folder", is_dirty=True))

    children = list(row)
    assert [c._props.get("name") for c in children if isinstance(c, ui.icon)] == ["folder"]
    assert any("bg-amber-400" in c.classes for c in children)
    assert not [c for c in children if isinstance(c, ui.label)]


@pytest.mark.unit
@pytest.mark.anyio
async def test_an_editor_toolbar_has_the_toolbar_look(user: User) -> None:
    row = await _render(user, hui.editor_toolbar)

    assert "hw-editor-toolbar" in row.classes
    assert row.style["min-height"] == "32px"
    assert row.style["background"] == "var(--hw-bg-surface)"
    assert row.style["border-bottom"] == "1px solid var(--hw-border)"


# A Tailwind border class with no colour: preflight leaves it currentColor, a near-white line.
_BARE_BORDER = re.compile(r"""\.classes\([^)]*["' ]border(-[btlrxy])?(?=["' ])""")


@pytest.mark.unit
def test_no_editor_draws_a_bare_tailwind_border() -> None:
    files = [
        *_REPO.glob("barn/*/*/editors/*.py"),
        *(_REPO / "packages/haywire-core/src/haywire/ui/app").glob("*.py"),
    ]
    hits = [
        f"{path.relative_to(_REPO)}:{number}"
        for path in files
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if _BARE_BORDER.search(line)
    ]

    assert not hits, f"bare Tailwind border (draws in the text colour): {hits}"
