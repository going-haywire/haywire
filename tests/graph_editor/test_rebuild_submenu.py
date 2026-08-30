"""The "Rebuild" submenu: one row on ``SelectionMenu`` over three commands.

Registration is pinned in ``tests/ui/test_canvas_handlers/test_selection_panels_unified.py``;
what needs a *render* is the part that fails silently — a hosting row greys
itself retroactively when its body draws nothing (``SubmenuRow.__exit__``), so
the row being live is a fact about the leaf counter, not about the decorator.
Rendered through the real ``render_panel`` + ``PanelRegistry``, inside the
ambient sibling group a context-menu host opens, exactly as the popup does.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.core.library.identity import LibraryIdentity
from haywire.ui import elements as hui
from haywire.ui.panel import PanelRegistry
from haywire.ui.panel.host_rendering import render_panel
from haywire.ui.panel.layout import PanelLayout

from tests.protocol_stubs import stub_for

from haybale_graph_editor.surfaces import SelectionActions
from haybale_graph_editor.panels.graph.menu.selection.selection import (
    RebuildSelectionMenuPanel,
    RedrawSelectionMenuPanel,
    ResetSelectionMenuPanel,
    RevalidateSelectionMenuPanel,
)

_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="graph editor test",
    version="0.0.1",
    folder_path="/tmp/rebuild-submenu-test",
    module_name="haybale_graph_editor",
    name="graph_editor",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


def _ctx(nodes):  # untyped, like test_render_surface's own stub: a SessionContext stand-in
    edit = SimpleNamespace(selected_nodes=set(nodes), selected_edges=set())
    data = MagicMock()
    data.__getitem__.return_value = edit
    return SimpleNamespace(data=data, app=MagicMock(), session_id="t", can_access=lambda required: True)


def _actions_stub():
    """A real object, not a MagicMock: ``render_surface`` validates the chosen
    host with ``isinstance`` against a runtime Protocol, and 3.12 resolves those
    members statically — a MagicMock's lazy attributes do not satisfy it.

    Derived from ``SelectionActions`` rather than hand-listed, so a verb added
    to the Protocol does not break this file. See ``tests/protocol_stubs.py``.
    """
    return stub_for(SelectionActions)


def _registry() -> PanelRegistry:
    registry = PanelRegistry()
    for cls in (
        RedrawSelectionMenuPanel,
        RevalidateSelectionMenuPanel,
        ResetSelectionMenuPanel,
    ):
        registry._register_class(cls, _FAKE_LIBRARY_IDENTITY)
    return registry


def _labels(element: ui.element) -> list[str]:
    """Every label text in the subtree, in render order."""
    found: list[str] = []
    for child in element.descendants():
        text = getattr(child, "text", None)
        if isinstance(text, str) and text:
            found.append(text)
    return found


@pytest.mark.anyio
async def test_rebuild_row_hosts_the_three_commands_and_stays_live(user: User) -> None:
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with hui.open_flyout_group():
            layout = PanelLayout(ui.column())
            render_panel(
                RebuildSelectionMenuPanel,
                _ctx({"n1"}),
                layout,
                actions_host=_actions_stub(),
                registry=_registry(),
            )
            captured["layout"] = layout

    await user.open("/")

    layout: PanelLayout = captured["layout"]  # type: ignore[assignment]
    labels = _labels(layout.container)
    assert "Rebuild" in labels
    for command in ("Redraw Node", "Revalidate Node", "Reset Node"):
        assert command in labels, f"{command!r} should render inside the Rebuild flyout"

    # The row drew a body, so it must not have greyed itself on exit.
    rows = [c for c in layout.container.descendants() if "hw-flyout-row" in c._classes]
    assert rows, "the submenu row itself should have rendered"
    assert "hw-disabled" not in rows[0]._classes

    # Row and leaves are the same element, so the menu reads as one thing.
    menu_rows = [c for c in layout.container.descendants() if "hw-menu-row" in c._classes]
    assert len(menu_rows) == 4, "the Rebuild row plus its three commands"


@pytest.mark.anyio
async def test_rebuild_row_greys_without_a_selection(user: User) -> None:
    """poll() is False, so the host calls draw_disabled(): a row that does not
    expand — the same fixed-shape convention every command in this menu keeps."""
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with hui.open_flyout_group():
            layout = PanelLayout(ui.column())
            ctx = _ctx(set())
            assert RebuildSelectionMenuPanel.poll(ctx) is False
            render_panel(
                RebuildSelectionMenuPanel,
                ctx,
                layout,
                actions_host=_actions_stub(),
                registry=_registry(),
                disabled=True,
            )
            captured["layout"] = layout

    await user.open("/")

    layout: PanelLayout = captured["layout"]  # type: ignore[assignment]
    rows = [c for c in layout.container.descendants() if "hw-flyout-row" in c._classes]
    assert rows, "the greyed row should still render — an inapplicable command greys"
    assert "hw-disabled" in rows[0]._classes
    assert "Redraw Node" not in _labels(layout.container)
