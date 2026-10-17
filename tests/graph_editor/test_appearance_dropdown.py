"""The toolbar's Appearance dropdown: SelectionToolbar -> NodeAppearance.

The nesting itself is ordinary (ADR-0029, same as the Rebuild submenu); what is
worth pinning is what makes *this* one a dropdown rather than a menu — a
content surface whose rows are the live ``appearance`` slice of the node's own
props bag, gated on there being a node at all.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.core.access import LevelMode
from haywire.core.library.identity import LibraryIdentity
from haywire.core.node.properties import NodeProperties
from haywire.ui import elements as hui
from haywire.ui.elements.elements import MENU_ROW_CLASS
from haywire.ui.panel import PanelRegistry
from haywire.ui.panel.host_rendering import render_panel
from haywire.ui.panel.layout import PanelLayout

from haybale_graph_editor.panels.graph.toolbar.appearance import (
    APPEARANCE_CATEGORY,
    AppearanceToolbarPanel,
    NodeAppearancePanel,
)
from haybale_graph_editor.surfaces import NodeAppearance, SelectionToolbar

_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="graph editor test",
    version="0.0.1",
    folder_path="/tmp/appearance-dropdown-test",
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


def _node(*, reroute: bool = False):
    behavior = SimpleNamespace(is_reroute_node=reroute)
    return SimpleNamespace(props=NodeProperties(), behavior=behavior)


def _ctx(with_node=False, *, nodes=None, edges=()):  # untyped stand-in for SessionContext
    """A selection of *nodes* (id -> node) and edge ids; ``with_node`` selects one plain node."""
    if nodes is None:
        nodes = {"n1": _node()} if with_node else {}
    graph = SimpleNamespace(
        get_node_wrapper=lambda node_id: SimpleNamespace(node=nodes[node_id]) if node_id in nodes else None,
        get_edge_wrapper=lambda _edge_id: None,
    )
    edit = SimpleNamespace(
        active_node=None,
        active_graph=graph,
        active_mode=LevelMode.EDIT,
        active_route=MagicMock(),  # a level is open; the form draws only with a route
        selected_nodes=set(nodes),
        selected_edges=set(edges),
    )
    data = MagicMock()
    data.__getitem__.return_value = edit
    return SimpleNamespace(
        data=data,
        app=MagicMock(),
        session_id="t",
        can_access=lambda required: True,
        developer_mode=False,
    )


def _registry() -> PanelRegistry:
    registry = PanelRegistry()
    registry._register_class(NodeAppearancePanel, _FAKE_LIBRARY_IDENTITY)
    return registry


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


def test_the_icon_sits_on_the_toolbar_and_hosts_the_appearance_surface():
    assert AppearanceToolbarPanel.class_identity.surface is SelectionToolbar
    assert AppearanceToolbarPanel.class_identity.hosts == (NodeAppearance,)
    assert NodeAppearancePanel.class_identity.surface is NodeAppearance


def test_the_appearance_surface_declares_no_contract():
    """Its panels edit the node's own bag; there is no verb for a host."""
    assert NodeAppearance.provides is None
    assert NodeAppearance.presentation is None  # a dropdown, not a properties tab


def test_it_polls_for_a_node_not_merely_a_selection():
    """SelectionToolbar.poll is "something is selected", which an edges-only
    selection satisfies — there is nothing to style without a node."""
    assert AppearanceToolbarPanel.poll(_ctx(with_node=True)) is True
    assert AppearanceToolbarPanel.poll(_ctx(edges=["e1"])) is False
    assert NodeAppearancePanel.poll(_ctx(edges=["e1"])) is False


def test_a_selection_with_edges_hides_it():
    """Cross-kind: nodes and edges together have no shared appearance."""
    assert AppearanceToolbarPanel.poll(_ctx(with_node=True, edges=["e1"])) is False


# ---------------------------------------------------------------------------
# What it renders
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_the_dropdown_renders_the_appearance_slice_and_stays_live(user: User) -> None:
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with hui.open_flyout_group():
            layout = PanelLayout(ui.column())
            render_panel(
                AppearanceToolbarPanel,
                _ctx(with_node=True),
                layout,
                actions_host=MagicMock(),
                registry=_registry(),
            )
            captured["layout"] = layout

    await user.open("/")

    layout: PanelLayout = captured["layout"]  # type: ignore[assignment]
    descendants = list(layout.container.descendants())

    fields = [el._props["data-field"] for el in descendants if getattr(el, "_props", {}).get("data-field")]
    assert fields, "the appearance fields should have rendered inside the dropdown"
    appearance_fields = {
        name
        for name, defn in NodeProperties._settings_descriptors().items()
        if defn._category == APPEARANCE_CATEGORY
    }
    assert set(fields) == appearance_fields, "exactly the appearance slice, nothing else"

    # A dropdown holds content, so nothing here is a menu row...
    assert not [el for el in descendants if MENU_ROW_CLASS in el._classes]
    # ...and the icon stayed live (a panel drew inside it).
    buttons = [el for el in descendants if isinstance(el, ui.button)]
    assert buttons, "the dropdown anchor should have rendered"
    assert "hw-disabled" not in buttons[0]._classes


@pytest.mark.anyio
async def test_nothing_renders_without_a_node(user: User) -> None:
    """An edges-only selection is cross-kind for Appearance: the icon is not
    there at all, not even greyed."""
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with hui.open_flyout_group():
            layout = PanelLayout(ui.column())
            render_panel(
                AppearanceToolbarPanel,
                _ctx(edges=["e1"]),
                layout,
                actions_host=MagicMock(),
                registry=_registry(),
                disabled=True,
            )
            captured["layout"] = layout

    await user.open("/")

    layout: PanelLayout = captured["layout"]  # type: ignore[assignment]
    assert not list(layout.container.descendants())
