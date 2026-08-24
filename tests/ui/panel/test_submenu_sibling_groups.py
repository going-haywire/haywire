# tests/ui/panel/test_submenu_sibling_groups.py
"""Sibling-group mechanics (opening one row closes another), proven through
real ``@panel``-decorated classes rendered via ``render_surface`` — not the
bare ``hui.submenu_row`` primitive ``tests/ui/test_flyout_nesting.py`` uses.

That file proves the *primitive* shares one sibling group per level
regardless of which caller constructs a row (Task A, predates real panels).
This file proves the same holds once real, mutually-blind panels are the
callers: the group belongs to the container (a popup, or a hosting panel's
render_surface() call), never to the panel authoring one row — a per-panel
group is the bug a naive implementation reintroduces, and it needs panels
that have genuinely never heard of each other to catch it.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from haywire.core.library.identity import LibraryIdentity
from haywire.ui import elements as hui
from haywire.ui.elements.flyout import FLYOUT_OPEN_DELAY_S, SubmenuRow, open_flyout_group
from haywire.ui.panel import BasePanel, PanelRegistry, panel
from haywire.ui.panel.host_rendering import render_panel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.surface import Surface


_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="fake",
    version="0.1",
    folder_path="/tmp/fake",
    module_name="fake",
    name="fake",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


def _hover(user: User, element: ui.element) -> None:
    UserInteraction(user, {element}, None).trigger("mouseenter")


def _make_ctx():
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    return SimpleNamespace(
        data=MagicMock(), app=MagicMock(), session_id="t", can_access=lambda required: True
    )


# ---------------------------------------------------------------------------
# Two sibling rows, ONE surface — the per-panel-group bug
# ---------------------------------------------------------------------------


class _OneSurface(Surface):
    id = "sibling_group_test_one_surface"


@pytest.mark.unit
@pytest.mark.anyio
async def test_two_sibling_rows_on_one_surface_opening_one_closes_the_other(user: User) -> None:
    """Two panels on the SAME surface, each drawing its own submenu_row. They
    are registered independently (neither imports or references the other) —
    exactly the shape a per-panel sibling group would silently break, since
    both rows land in the popup's one ambient group only because the HOST
    pushed it, not because either panel coordinated with its neighbour."""

    captured: dict[str, SubmenuRow] = {}

    @panel(surface=_OneSurface, label="RowA", order=10, registry_id="sibling_test_row_a")
    class _RowAPanel(BasePanel):
        def draw(self, ctx, layout):
            with layout:
                with hui.submenu_row("Row A") as row:
                    ui.label("A content")
                captured["row_a"] = row

    @panel(surface=_OneSurface, label="RowB", order=20, registry_id="sibling_test_row_b")
    class _RowBPanel(BasePanel):
        def draw(self, ctx, layout):
            with layout:
                with hui.submenu_row("Row B") as row:
                    ui.label("B content")
                captured["row_b"] = row

    registry = PanelRegistry()
    registry._register_class(_RowAPanel, _FAKE_LIBRARY_IDENTITY)
    registry._register_class(_RowBPanel, _FAKE_LIBRARY_IDENTITY)

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with ui.column() as container:
                layout = PanelLayout(container)
                for cls in registry.get_panels(_OneSurface):
                    render_panel(cls, _make_ctx(), layout, registry=registry)

    await user.open("/")

    row_a = captured["row_a"]
    row_b = captured["row_b"]
    assert row_a._menu is not None
    assert row_b._menu is not None

    _hover(user, row_a._row)
    await asyncio.sleep(FLYOUT_OPEN_DELAY_S + 0.08)
    assert row_a._menu.value is True

    _hover(user, row_b._row)
    await asyncio.sleep(FLYOUT_OPEN_DELAY_S + 0.08)
    assert row_b._menu.value is True
    assert row_a._menu.value is False, (
        "opening Row B must close Row A — both panels share one sibling group "
        "even though neither references the other"
    )


# ---------------------------------------------------------------------------
# Two rows on DIFFERENT surfaces rendered into the same popup
# ---------------------------------------------------------------------------


class _RegionOneSurface(Surface):
    id = "sibling_group_test_region_one"


class _RegionTwoSurface(Surface):
    id = "sibling_group_test_region_two"


class _RootSurface(Surface):
    id = "sibling_group_test_root"


@pytest.mark.unit
@pytest.mark.anyio
async def test_two_rows_on_different_surfaces_in_the_same_popup_are_siblings(user: User) -> None:
    """The per-*surface* group case: RegionOne and RegionTwo are two DIFFERENT
    surfaces (mirroring GraphToolBar / GraphContextBody, both hosted by
    GraphContext into the one popup). A row on each must still share ONE
    sibling group — the group belongs to the container (the popup), not to
    either surface — or opening one region's row would leave the other's
    open."""

    captured: dict[str, SubmenuRow] = {}

    @panel(surface=_RegionOneSurface, label="RegionOneRow", registry_id="sibling_test_region_one_row")
    class _RegionOneRowPanel(BasePanel):
        def draw(self, ctx, layout):
            with layout:
                with hui.submenu_row("Region One Row") as row:
                    ui.label("region one content")
                captured["region_one_row"] = row

    @panel(surface=_RegionTwoSurface, label="RegionTwoRow", registry_id="sibling_test_region_two_row")
    class _RegionTwoRowPanel(BasePanel):
        def draw(self, ctx, layout):
            with layout:
                with hui.submenu_row("Region Two Row") as row:
                    ui.label("region two content")
                captured["region_two_row"] = row

    @panel(
        surface=_RootSurface,
        hosts=(_RegionOneSurface, _RegionTwoSurface),
        label="RootLayout",
        registry_id="sibling_test_root_layout",
    )
    class _RootLayoutPanel(BasePanel):
        def draw(self, ctx, layout):
            with layout:
                self.render_surface(_RegionOneSurface, ctx)
                self.render_surface(_RegionTwoSurface, ctx)

    registry = PanelRegistry()
    for cls in (_RegionOneRowPanel, _RegionTwoRowPanel, _RootLayoutPanel):
        registry._register_class(cls, _FAKE_LIBRARY_IDENTITY)

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with ui.column() as container:
                layout = PanelLayout(container)
                render_panel(_RootLayoutPanel, _make_ctx(), layout, registry=registry)

    await user.open("/")

    region_one_row = captured["region_one_row"]
    region_two_row = captured["region_two_row"]
    assert region_one_row._menu is not None
    assert region_two_row._menu is not None

    _hover(user, region_one_row._row)
    await asyncio.sleep(FLYOUT_OPEN_DELAY_S + 0.08)
    assert region_one_row._menu.value is True

    _hover(user, region_two_row._row)
    await asyncio.sleep(FLYOUT_OPEN_DELAY_S + 0.08)
    assert region_two_row._menu.value is True
    assert region_one_row._menu.value is False, (
        "opening Region Two's row must close Region One's — the sibling "
        "group belongs to the container (the popup GraphContextPanel builds "
        "for both regions), not to either surface"
    )
