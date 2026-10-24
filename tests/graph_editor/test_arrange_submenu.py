"""The "Arrange" submenu: one row on ``SelectionMenu`` over the four stacking-order verbs.

Rendered through the real ``render_panel`` + ``PanelRegistry``, inside the ambient sibling group
a context-menu host opens, as ``test_rebuild_submenu.py`` does for "Rebuild".
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haybale_graph_editor.editors.graph_canvas.handlers.context_menu import SessionContextMenuProvider
from haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar import SelectionToolbarProvider
from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haybale_graph_editor.panels.graph.menu.selection.arrange import (
    ArrangeSelectionMenuPanel,
    BringForwardMenuPanel,
    BringToFrontMenuPanel,
    SendBackwardMenuPanel,
    SendToBackMenuPanel,
)
from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.surfaces import SelectionActions, SelectionArrangeMenu, SelectionMenu
from haywire.core.access import AccessTier
from haywire.core.graph.stacking import Restack
from haywire.core.library.identity import LibraryIdentity
from haywire.core.node.layout import STAGE
from haywire.ui import elements as hui
from haywire.ui.components.graph.event_definitions import RestackEvent
from haywire.ui.panel import PanelRegistry
from haywire.ui.panel.host_rendering import render_panel
from haywire.ui.panel.layout import PanelLayout

from tests.conftest import edit_route
from tests.protocol_stubs import stub_for

_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="graph editor test",
    version="0.0.1",
    folder_path="/tmp/arrange-submenu-test",
    module_name="haybale_graph_editor",
    name="graph_editor",
)

_LEAVES = [
    (BringToFrontMenuPanel, "Bring to Front", Restack.FRONT),
    (BringForwardMenuPanel, "Bring Forward", Restack.FORWARD),
    (SendBackwardMenuPanel, "Send Backward", Restack.BACKWARD),
    (SendToBackMenuPanel, "Send to Back", Restack.BACK),
]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


def _ctx(nodes: set[str]):
    graph = SimpleNamespace(get_node_wrapper=lambda nid: SimpleNamespace() if nid in nodes else None)
    edit = SimpleNamespace(
        selected_nodes=set(nodes), selected_edges=set(), active_node=None, active_graph=graph
    )
    data = MagicMock()
    data.__getitem__.side_effect = lambda key: edit if key is EditState else MagicMock()
    return SimpleNamespace(data=data, app=MagicMock(), session_id="t", can_access=lambda required: True)


def _registry() -> PanelRegistry:
    registry = PanelRegistry()
    for cls, _, _ in _LEAVES:
        registry._register_class(cls, _FAKE_LIBRARY_IDENTITY)
    return registry


def _labels(element: ui.element) -> list[str]:
    return [t for c in element.descendants() if isinstance(t := getattr(c, "text", None), str) and t]


def _click_row(element: ui.element, label: str) -> None:
    """Fire the click listener of the menu row whose label is ``label``."""
    for row in element.descendants():
        if "hw-menu-row" not in row._classes:
            continue
        if _labels(row)[:1] != [label]:  # the Arrange row holds its leaves' labels too
            continue
        handlers = [lst.handler for lst in row._event_listeners.values() if lst.type == "click"]
        assert handlers, f"{label!r} row has no click handler"
        handler = handlers[0]
        assert handler is not None
        handler(None)
        return
    raise AssertionError(f"no menu row labelled {label!r}")


async def _render(user: User, nodes: set[str], stub: Any, *, disabled: bool = False) -> PanelLayout:
    captured: dict[str, PanelLayout] = {}

    @ui.page("/")
    def page() -> None:
        with hui.open_flyout_group():
            layout = PanelLayout(ui.column())
            render_panel(
                ArrangeSelectionMenuPanel,
                _ctx(nodes),
                layout,
                actions_host=stub,
                registry=_registry(),
                disabled=disabled,
            )
            captured["layout"] = layout

    await user.open("/")
    return captured["layout"]


@pytest.mark.anyio
async def test_arrange_row_hosts_the_four_verbs_and_stays_live(user: User) -> None:
    layout = await _render(user, {"n1"}, stub_for(SelectionActions))

    labels = _labels(layout.container)
    assert "Arrange" in labels
    for _, label, _ in _LEAVES:
        assert label in labels, f"{label!r} should render inside the Arrange flyout"
    rows = [c for c in layout.container.descendants() if "hw-flyout-row" in c._classes]
    assert rows
    assert "hw-disabled" not in rows[0]._classes
    menu_rows = [c for c in layout.container.descendants() if "hw-menu-row" in c._classes]
    assert len(menu_rows) == 5, "the Arrange row plus its four verbs"


@pytest.mark.anyio
async def test_arrange_row_greys_without_a_selection(user: User) -> None:
    assert ArrangeSelectionMenuPanel.poll(_ctx(set())) is False
    layout = await _render(user, set(), stub_for(SelectionActions), disabled=True)

    rows = [c for c in layout.container.descendants() if "hw-flyout-row" in c._classes]
    assert rows
    assert "hw-disabled" in rows[0]._classes
    assert "Bring to Front" not in _labels(layout.container)


@pytest.mark.anyio
async def test_each_leaf_calls_restack_with_its_verb(user: User) -> None:
    stub = stub_for(SelectionActions)
    layout = await _render(user, {"n1"}, stub)

    for _, label, _ in _LEAVES:
        _click_row(layout.container, label)
    assert [call for call in stub.calls if call[0] == "restack_selection"] == [
        ("restack_selection", (how,)) for _, _, how in _LEAVES
    ]


def test_the_arrange_panels_need_edit_and_sit_where_they_should():
    assert ArrangeSelectionMenuPanel.class_identity.surface is SelectionMenu
    assert ArrangeSelectionMenuPanel.class_identity.hosts == (SelectionArrangeMenu,)
    assert SelectionArrangeMenu.id == "selection-arrange"
    assert SelectionArrangeMenu.provides is SelectionActions
    for cls in (ArrangeSelectionMenuPanel, *(leaf for leaf, _, _ in _LEAVES)):
        assert cls.class_identity.requires is AccessTier.EDIT
    for leaf, _, _ in _LEAVES:
        assert leaf.class_identity.surface is SelectionArrangeMenu


def test_restack_selection_emits_a_restack_event():
    provider: Any = object.__new__(SessionContextMenuProvider)
    provider._context = _ctx({"a", "b"})
    provider._emit = MagicMock()

    provider.restack_selection(Restack.FRONT)

    (event,) = (c.args[0] for c in provider._emit.call_args_list)
    assert isinstance(event, RestackEvent)
    assert event.how == "front"
    assert sorted(event.node_ids) == ["a", "b"]


def test_the_toolbar_provider_forwards_restack():
    menu_provider = MagicMock()
    toolbar: Any = object.__new__(SelectionToolbarProvider)
    toolbar._menu_provider = menu_provider
    toolbar.restack_selection(Restack.BACK)
    menu_provider.restack_selection.assert_called_once_with(Restack.BACK)


def test_a_restack_event_reaches_the_editor_on_the_canvas_channel():
    editor = MagicMock()
    layer = VisualLayerHandlers(
        graph=MagicMock(),
        route=edit_route(editor),
        skin_factory=MagicMock(),
        canvas_vue=MagicMock(),
        channel=STAGE,
    )
    layer.process_restack(RestackEvent(node_ids=["a"], how="forward"))
    editor.restack_nodes.assert_called_once_with(["a"], Restack.FORWARD, STAGE)
