"""``hui.menu_row`` — one element, one CSS block, one set of theme tokens.

The point of this element is that a menu command's look exists in exactly one
place. These tests pin the three halves of that claim:

1. the element itself sets no colour or typography (it only marks the row),
2. ``hui.submenu_row`` *is* a ``menu_row``, so a command and the submenu row
   beside it cannot drift, and
3. every value in the ``.hw-menu-row`` CSS block reads a ``--hw-menu-row-*``
   token that a ``WorkbenchTheme`` can set.
"""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.ui import elements as hui
from haywire.ui.app.shell import STATIC_CSS
from haywire.ui.elements.elements import MENU_ROW_CLASS, MENU_ROW_ICON_CLASS
from haywire.ui.elements.flyout import open_flyout_group
from haywire.ui.themes.workbench import WorkbenchTheme


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


# ---------------------------------------------------------------------------
# 1. The element marks the row and styles nothing
# ---------------------------------------------------------------------------

# Anything that would put a colour, size or weight on the row itself — the
# per-call-site styling this element exists to abolish.
_LOOK_CLASS = re.compile(r"^(text-(xs|sm|base|lg)|font-|hw-text-|text-[a-z]+-\d{3}|uppercase)")


@pytest.mark.unit
@pytest.mark.anyio
async def test_menu_row_carries_the_marker_and_no_look_of_its_own(user: User) -> None:
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        captured["row"] = hui.menu_row("Delete Node", icon="delete")

    await user.open("/")

    row: ui.row = captured["row"]  # type: ignore[assignment]
    assert MENU_ROW_CLASS in row._classes
    offenders = [c for c in row._classes if _LOOK_CLASS.match(c)]
    assert not offenders, f"a menu row must not carry its own look: {offenders}"
    assert not row._style, f"a menu row must not carry inline style: {row._style}"

    icons = [c for c in row.descendants() if MENU_ROW_ICON_CLASS in c._classes]
    assert len(icons) == 1, "the leading icon must be marked so the token can reach it"


@pytest.mark.unit
@pytest.mark.anyio
async def test_disabled_menu_row_greys_and_does_not_fire(user: User) -> None:
    clicks: list[int] = []
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        captured["row"] = hui.menu_row(
            "Delete", icon="delete", on_click=lambda: clicks.append(1), enabled=False
        )

    await user.open("/")

    row: ui.row = captured["row"]  # type: ignore[assignment]
    assert "hw-disabled" in row._classes
    assert row._style.get("opacity") == "0.4"
    assert row._style.get("pointer-events") == "none"
    assert clicks == []


# ---------------------------------------------------------------------------
# 2. A submenu row IS a menu row
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.anyio
async def test_submenu_row_anchor_is_a_menu_row(user: User) -> None:
    """The anti-drift guarantee: the row that expands and the rows beside it
    are the same element, so styling one styles the other."""
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.submenu_row("Rebuild", icon="refresh") as row:
                pass
        captured["row"] = row

    await user.open("/")

    row: hui.SubmenuRow = captured["row"]  # type: ignore[assignment]
    anchor = row._row
    assert MENU_ROW_CLASS in anchor._classes
    assert "hw-flyout-row" in anchor._classes  # plus the "this one expands" marker
    # Leading icon and chevron both follow the icon token.
    icons = [c for c in anchor.descendants() if MENU_ROW_ICON_CLASS in c._classes]
    assert len(icons) == 2


# ---------------------------------------------------------------------------
# 3. The one CSS block is themable
# ---------------------------------------------------------------------------


def test_the_menu_row_block_exists_once_and_is_token_driven():
    block = re.search(r"\.hw-menu-row \{(.*?)\}", STATIC_CSS, re.S)
    assert block is not None, ".hw-menu-row must be styled in the shell's static CSS"
    body = block.group(1)
    for prop in ("color", "font-size", "font-weight", "text-transform"):
        declaration = re.search(rf"{prop}:\s*([^;]+);", body)
        assert declaration is not None, f"{prop} missing from the .hw-menu-row block"
        assert "--hw-menu-row-" in declaration.group(1), (
            f"{prop} must read a --hw-menu-row-* token so a theme can set it, got {declaration.group(1)!r}"
        )


def test_every_menu_row_token_is_settable_from_a_theme():
    """A token used by the CSS but absent from the theme map could never be
    themed — the whole point of routing the look through tokens."""
    used = set(re.findall(r"var\((--hw-menu-row-[a-z-]+)", STATIC_CSS))
    mapped = set(WorkbenchTheme._CSS_TOKEN_MAP.values())
    assert used, "the menu-row block should read --hw-menu-row-* tokens"
    assert used <= mapped, f"not settable from a WorkbenchTheme: {sorted(used - mapped)}"


def test_a_theme_emits_the_menu_row_tokens_it_sets():
    class _MenuTheme(WorkbenchTheme):
        menu_row_text = "#ff0000"
        menu_row_text_transform = "uppercase"

    css_vars = _MenuTheme().to_css_vars()
    assert css_vars["--hw-menu-row-text"] == "#ff0000"
    assert css_vars["--hw-menu-row-text-transform"] == "uppercase"
    # Unset ones simply don't appear — the CSS fallback covers them.
    assert "--hw-menu-row-hover-bg" not in css_vars
