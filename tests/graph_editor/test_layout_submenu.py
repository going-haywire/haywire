"""The "Layout" and "Select" submenus of ``SelectionMenu``, and "Arrange All" on the canvas menu.

Rendered through the real ``render_panel`` + ``PanelRegistry``, as ``test_arrange_submenu.py``
does for the stacking-order "Arrange" submenu.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haybale_graph_editor.editors.graph_canvas.handlers.context_menu import SessionContextMenuProvider
from haybale_graph_editor.editors.graph_canvas.handlers.selection import SelectionHandlers
from haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar import SelectionToolbarProvider
from haybale_graph_editor.panels.graph.menu.graph.context import ArrangeAllMenuPanel
from haybale_graph_editor.panels.graph.menu.selection.layout import (
    ArrangeDownstreamMenuPanel,
    ArrangeFlowMenuPanel,
    ArrangeUpstreamMenuPanel,
    LayoutSelectionMenuPanel,
    SelectDownstreamMenuPanel,
    SelectFlowSelectionMenuPanel,
    SelectUpstreamMenuPanel,
)
from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.surfaces import (
    GraphMoreActions,
    SelectionActions,
    SelectionLayoutMenu,
    SelectionMenu,
    SelectionSelectMenu,
)
from haywire.core.access import AccessTier
from haywire.core.graph.arrange import ArrangeGaps, ArrangeScope
from haywire.core.library.identity import LibraryIdentity
from haywire.core.node.layout import PATCH, STAGE
from haywire.ui import elements as hui
from haywire.ui.components.graph.event_definitions import ArrangeNodesEvent, SelectConnectedEvent
from haywire.ui.panel import BasePanel, PanelRegistry
from haywire.ui.panel.host_rendering import render_panel
from haywire.ui.panel.layout import PanelLayout

from tests.conftest import edit_route
from tests.protocol_stubs import stub_for

_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="graph editor test",
    version="0.0.1",
    folder_path="/tmp/layout-submenu-test",
    module_name="haybale_graph_editor",
    name="graph_editor",
)

_ARRANGE: list[tuple[type[BasePanel], str, ArrangeScope]] = [
    (ArrangeFlowMenuPanel, "Arrange Flow", ArrangeScope.FLOW),
    (ArrangeDownstreamMenuPanel, "Arrange Downstream", ArrangeScope.DOWNSTREAM),
    (ArrangeUpstreamMenuPanel, "Arrange Upstream", ArrangeScope.UPSTREAM),
]
_SELECT: list[tuple[type[BasePanel], str, ArrangeScope]] = [
    (SelectDownstreamMenuPanel, "Select Downstream", ArrangeScope.DOWNSTREAM),
    (SelectUpstreamMenuPanel, "Select Upstream", ArrangeScope.UPSTREAM),
]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


def _ctx(nodes: set[str], edges: set[str] = frozenset()):  # type: ignore[assignment]
    graph = SimpleNamespace(get_node_wrapper=lambda nid: SimpleNamespace() if nid in nodes else None)
    edit = SimpleNamespace(
        selected_nodes=set(nodes), selected_edges=set(edges), active_node=None, active_graph=graph
    )
    data = MagicMock()
    data.__getitem__.side_effect = lambda key: edit if key is EditState else MagicMock()
    return SimpleNamespace(data=data, app=MagicMock(), session_id="t", can_access=lambda required: True)


def _registry() -> PanelRegistry:
    registry = PanelRegistry()
    for cls, _, _ in (*_ARRANGE, *_SELECT):
        registry._register_class(cls, _FAKE_LIBRARY_IDENTITY)
    return registry


def _labels(element: ui.element) -> list[str]:
    return [t for c in element.descendants() if isinstance(t := getattr(c, "text", None), str) and t]


def _click_row(element: ui.element, label: str) -> None:
    """Fire the click listener of the menu row whose label is ``label``."""
    for row in element.descendants():
        if "hw-menu-row" not in row._classes or _labels(row)[:1] != [label]:
            continue
        handlers = [lst.handler for lst in row._event_listeners.values() if lst.type == "click"]
        assert handlers, f"{label!r} row has no click handler"
        handler = handlers[0]
        assert handler is not None
        handler(None)
        return
    raise AssertionError(f"no menu row labelled {label!r}")


async def _render(user: User, host, nodes: set[str], stub: Any, *, disabled: bool = False) -> PanelLayout:
    captured: dict[str, PanelLayout] = {}

    @ui.page("/")
    def page() -> None:
        with hui.open_flyout_group():
            layout = PanelLayout(ui.column())
            render_panel(
                host, _ctx(nodes), layout, actions_host=stub, registry=_registry(), disabled=disabled
            )
            captured["layout"] = layout

    await user.open("/")
    return captured["layout"]


# ---------------------------------------------------------------------------
# Rows
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("host", "label", "leaves"),
    [(LayoutSelectionMenuPanel, "Layout", _ARRANGE), (SelectFlowSelectionMenuPanel, "Select", _SELECT)],
)
async def test_each_host_shows_its_verbs_for_one_node(user: User, host, label, leaves) -> None:
    layout = await _render(user, host, {"n1"}, stub_for(SelectionActions))

    labels = _labels(layout.container)
    assert label in labels
    for _, leaf_label, _ in leaves:
        assert leaf_label in labels
    rows = [c for c in layout.container.descendants() if "hw-flyout-row" in c._classes]
    assert rows
    assert "hw-disabled" not in rows[0]._classes


def test_select_and_the_directed_verbs_need_exactly_one_node() -> None:
    panels: list[type[BasePanel]] = [SelectFlowSelectionMenuPanel]
    panels += [leaf for leaf, _, _ in (*_ARRANGE[1:], *_SELECT)]
    for panel_cls in panels:
        assert panel_cls.poll(_ctx({"n1"})) is True
        assert panel_cls.poll(_ctx({"n1", "n2"})) is False
        assert panel_cls.poll(_ctx(set())) is False
        assert panel_cls.poll(_ctx({"n1"}, {"e1"})) is False


def test_layout_and_arrange_flow_take_one_or_more_nodes() -> None:
    panels: list[type[BasePanel]] = [LayoutSelectionMenuPanel, ArrangeFlowMenuPanel]
    for panel_cls in panels:
        assert panel_cls.poll(_ctx({"n1"})) is True
        assert panel_cls.poll(_ctx({"n1", "n2"})) is True
        assert panel_cls.poll(_ctx(set())) is False


@pytest.mark.anyio
async def test_with_two_nodes_only_arrange_flow_stays_live(user: User) -> None:
    stub = stub_for(SelectionActions)
    layout = await _render(user, LayoutSelectionMenuPanel, {"n1", "n2"}, stub)

    rows = {
        _labels(row)[0]: "hw-disabled" in row._classes
        for row in layout.container.descendants()
        if "hw-menu-row" in row._classes and _labels(row)
    }
    assert rows["Arrange Flow"] is False
    assert rows["Arrange Downstream"] is True
    assert rows["Arrange Upstream"] is True
    _click_row(layout.container, "Arrange Flow")
    assert [c for c in stub.calls if c[0] == "arrange_from"] == [
        ("arrange_from", (["n1", "n2"], ArrangeScope.FLOW))
    ]


@pytest.mark.anyio
async def test_the_select_row_greys_for_two_nodes(user: User) -> None:
    layout = await _render(
        user, SelectFlowSelectionMenuPanel, {"n1", "n2"}, stub_for(SelectionActions), disabled=True
    )

    rows = [c for c in layout.container.descendants() if "hw-flyout-row" in c._classes]
    assert rows
    assert "hw-disabled" in rows[0]._classes
    assert "Select Downstream" not in _labels(layout.container)


@pytest.mark.anyio
async def test_each_leaf_calls_its_verb_with_its_scope(user: User) -> None:
    stub = stub_for(SelectionActions)
    layout = await _render(user, LayoutSelectionMenuPanel, {"n1"}, stub)
    for _, label, _ in _ARRANGE:
        _click_row(layout.container, label)
    assert [c for c in stub.calls if c[0] == "arrange_from"] == [
        ("arrange_from", (["n1"], scope)) for _, _, scope in _ARRANGE
    ]


@pytest.mark.anyio
async def test_each_select_leaf_calls_select_from(user: User) -> None:
    stub = stub_for(SelectionActions)
    layout = await _render(user, SelectFlowSelectionMenuPanel, {"n1"}, stub)
    for _, label, _ in _SELECT:
        _click_row(layout.container, label)
    assert [c for c in stub.calls if c[0] == "select_from"] == [
        ("select_from", ("n1", scope)) for _, _, scope in _SELECT
    ]


def test_the_panels_need_edit_and_sit_where_they_should() -> None:
    assert LayoutSelectionMenuPanel.class_identity.surface is SelectionMenu
    assert LayoutSelectionMenuPanel.class_identity.hosts == (SelectionLayoutMenu,)
    assert SelectFlowSelectionMenuPanel.class_identity.hosts == (SelectionSelectMenu,)
    assert ArrangeAllMenuPanel.class_identity.surface is GraphMoreActions
    for surface in (SelectionLayoutMenu, SelectionSelectMenu):
        assert surface.provides is SelectionActions
    for leaf, _, _ in _ARRANGE:
        assert leaf.class_identity.surface is SelectionLayoutMenu
    for leaf, _, _ in _SELECT:
        assert leaf.class_identity.surface is SelectionSelectMenu
    every: list[type[BasePanel]] = [
        LayoutSelectionMenuPanel,
        SelectFlowSelectionMenuPanel,
        ArrangeAllMenuPanel,
    ]
    for cls in every + [leaf for leaf, _, _ in (*_ARRANGE, *_SELECT)]:
        assert cls.class_identity.requires is AccessTier.EDIT


def test_arrange_all_needs_two_nodes() -> None:
    def ctx(n: int):
        edit = SimpleNamespace(active_graph=SimpleNamespace(node_wrappers=dict.fromkeys(range(n))))
        data = MagicMock()
        data.__getitem__.side_effect = lambda key: edit
        return SimpleNamespace(data=data)

    assert ArrangeAllMenuPanel.poll(ctx(2)) is True
    assert ArrangeAllMenuPanel.poll(ctx(1)) is False


# ---------------------------------------------------------------------------
# Providers and handlers
# ---------------------------------------------------------------------------


def _provider() -> Any:
    provider: Any = object.__new__(SessionContextMenuProvider)
    provider._context = _ctx({"a"})
    provider._emit = MagicMock()
    return provider


def test_the_menu_provider_emits_the_events() -> None:
    provider = _provider()
    provider.arrange_from(["a"], ArrangeScope.UPSTREAM)
    provider.select_from("a", ArrangeScope.DOWNSTREAM)
    provider.arrange_graph()
    events = [c.args[0] for c in provider._emit.call_args_list]
    assert events == [
        ArrangeNodesEvent(node_ids=["a"], scope="upstream"),
        SelectConnectedEvent(node_id="a", scope="downstream"),
        ArrangeNodesEvent(node_ids=[], scope="all"),
    ]


def test_the_toolbar_provider_forwards_the_verbs() -> None:
    menu_provider = MagicMock()
    toolbar: Any = object.__new__(SelectionToolbarProvider)
    toolbar._menu_provider = menu_provider
    toolbar.arrange_from(["a"], ArrangeScope.FLOW)
    toolbar.select_from("a", ArrangeScope.UPSTREAM)
    menu_provider.arrange_from.assert_called_once_with(["a"], ArrangeScope.FLOW)
    menu_provider.select_from.assert_called_once_with("a", ArrangeScope.UPSTREAM)


def _graph(locked=(), off_stage=()):
    """a -> b -> c; ``locked`` nodes are locked, ``off_stage`` nodes are not on stage."""

    def wrapper(n):
        props = SimpleNamespace(locked=n in locked, on_stage=n not in off_stage)
        return SimpleNamespace(node=SimpleNamespace(props=props))

    edges = {"e1": ("a", "b"), "e2": ("b", "c")}
    return SimpleNamespace(
        node_wrappers={n: wrapper(n) for n in "abc"},
        edge_wrappers={k: SimpleNamespace(source_node_id=s, sink_node_id=t) for k, (s, t) in edges.items()},
    )


def test_select_connected_replaces_the_selection_without_locked_nodes() -> None:
    handlers = SelectionHandlers(graph=_graph(locked=["c"]), route=MagicMock(), session_id="t")  # type: ignore[arg-type]
    handlers.selected_edges = {"e9"}
    handlers.process_select_connected(SelectConnectedEvent(node_id="a", scope="downstream"))
    assert handlers.selected_nodes == {"b"}
    assert handlers.selected_edges == set()


def test_select_connected_in_a_stage_canvas_keeps_to_on_stage_nodes() -> None:
    handlers = SelectionHandlers(
        graph=_graph(off_stage=["b"]),
        route=MagicMock(),
        session_id="t",
        channel=STAGE,  # type: ignore[arg-type]
    )
    handlers.process_select_connected(SelectConnectedEvent(node_id="c", scope="upstream"))
    assert handlers.selected_nodes == {"a"}


_ARRANGE_LAYOUT = "haybale_graph_editor.editors.graph_canvas.handlers.selection.arrange_layout"


def _arranging(editor, channel=PATCH, **graph) -> SelectionHandlers:
    return SelectionHandlers(
        graph=_graph(**graph),  # type: ignore[arg-type]
        route=edit_route(editor),
        session_id="t",
        channel=channel,
    )


def test_an_arrange_moves_the_computed_positions_then_selects_them() -> None:
    editor = MagicMock()
    handlers = _arranging(editor, locked=["c"])
    positions = {"b": {"x": 1.0, "y": 2.0}}
    with patch(_ARRANGE_LAYOUT, return_value=positions) as arrange:
        handlers.process_arrange(ArrangeNodesEvent(node_ids=["a"], scope="downstream"))
    arrange.assert_called_once_with(handlers.graph, ArrangeScope.DOWNSTREAM, ["a"], ArrangeGaps())
    editor.move_nodes_to.assert_called_once_with(positions, PATCH)
    # c is locked: not selected, and neither is the edge into it
    assert handlers.selected_nodes == {"a", "b"}
    assert handlers.selected_edges == {"e1"}


def test_an_arrange_that_moves_nothing_keeps_the_selection() -> None:
    editor = MagicMock()
    editor.move_nodes_to.return_value = False
    handlers = _arranging(editor)
    handlers.selected_nodes = {"a"}
    with (
        patch(_ARRANGE_LAYOUT, return_value={}),
        patch("haybale_graph_editor.editors.graph_canvas.handlers.selection.ui.notify"),
    ):
        handlers.process_arrange(ArrangeNodesEvent(node_ids=["a"], scope="flow"))
    assert handlers.selected_nodes == {"a"}


def test_a_stage_canvas_declines_to_arrange() -> None:
    editor = MagicMock()
    handlers = _arranging(editor, channel=STAGE)
    with patch("haybale_graph_editor.editors.graph_canvas.handlers.selection.ui.notify") as notify:
        handlers.process_arrange(ArrangeNodesEvent(node_ids=["a"], scope="flow"))
    editor.move_nodes_to.assert_not_called()
    notify.assert_called_once()
