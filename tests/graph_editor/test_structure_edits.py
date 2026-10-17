"""Port reorder and edge propagation reach the level's ``Editor`` through its edit route.

Both are undoable ``Editor`` actions, and both need level mode edit: a level below
it, or one a lock has dropped, refuses them and changes nothing.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

import pytest
from nicegui import Client, ui

from haybale_graph_editor.access import level_mode
from haybale_graph_editor.editors.graph_canvas.handlers.context_menu import SessionContextMenuProvider
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.access import AccessTier, LevelMode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.edit_route import EditRoute
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.types.enums import Propagation

from tests.conftest import edit_route, make_edge, make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"


def _noop_page() -> None:  # registration target for a headless Client
    pass


@pytest.fixture
def held_graph(library_system) -> Iterator[BaseGraph]:
    """A graph whose debounce never fires on its own."""
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    yield graph
    graph._validation.clear()
    graph.cleanup()


@pytest.fixture
def editor(library_system, held_graph: BaseGraph) -> Editor:
    return Editor(held_graph, library_system.get_node_factory())


def _ctx(route: EditRoute | None, **edit_fields: Any) -> Any:
    edit = SimpleNamespace(active_route=route, **edit_fields)
    return SimpleNamespace(data={EditState: edit})


def _locked_admin_route(editor: Editor) -> EditRoute:
    return EditRoute(lambda: editor, lambda: level_mode(AccessTier.ADMIN.satisfies, True))


# =============================================================================
# Ports panel reorder
# =============================================================================


@dataclass
class _Drop:
    old_index: int
    new_index: int


def _inlets(wrapper: Any) -> list[str]:
    ports = wrapper.node.ports
    return sorted((pid for pid, p in ports.items() if p.is_inlet()), key=lambda pid: ports[pid].order)


def _drop_last_first(wrapper: Any, route: EditRoute | None) -> list[str]:
    """Drag the last inlet to the front through the panel's handler; return the rendered ids."""
    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel

    rendered = _inlets(wrapper)
    drop = _Drop(old_index=len(rendered) - 1, new_index=0)
    NodePortsPanel()._on_reorder(wrapper.node, rendered, drop, _ctx(route))
    return rendered


def test_a_port_reorder_is_one_undo_step(held_graph, editor):
    wrapper = make_node(held_graph, _ADD)
    original = _inlets(wrapper)
    assert len(original) >= 2

    _drop_last_first(wrapper, edit_route(editor))

    assert _inlets(wrapper) == [original[-1], *original[:-1]]
    assert editor.undo() is True
    assert _inlets(wrapper) == original


@pytest.mark.parametrize("locked", [False, True], ids=["operate", "locked-admin"])
def test_reordering_ports_refuses_on_a_locked_level(held_graph, editor, locked: bool):
    wrapper = make_node(held_graph, _ADD)
    original = _inlets(wrapper)
    route = _locked_admin_route(editor) if locked else edit_route(editor, LevelMode.OPERATE)

    _drop_last_first(wrapper, route)

    assert _inlets(wrapper) == original
    assert editor.can_undo() is False


def test_reordering_ports_refuses_without_a_route(held_graph):
    wrapper = make_node(held_graph, _ADD)
    original = _inlets(wrapper)

    _drop_last_first(wrapper, None)

    assert _inlets(wrapper) == original


# =============================================================================
# Edge propagation
# =============================================================================


@pytest.fixture
def edge(held_graph):
    a = make_node(held_graph, _ADD, position=(0, 0))
    b = make_node(held_graph, _ADD, position=(300, 0))
    wrapper = make_edge(held_graph, a.node_id, "result", b.node_id, "value_a")
    held_graph.force_validation()
    assert wrapper.propagation is Propagation.EAGER
    return wrapper


def _toggle_through_the_menu(held_graph, route: EditRoute | None, edge_id: str) -> Propagation | None:
    provider = SimpleNamespace(
        _context=_ctx(route),
        _active_edge_wrapper=lambda eid: held_graph.get_edge_wrapper(eid),
    )
    return SessionContextMenuProvider.toggle_edge_propagation(cast(Any, provider), edge_id)


def test_a_propagation_toggle_is_one_undo_step(held_graph, editor, edge):
    assert _toggle_through_the_menu(held_graph, edit_route(editor), edge.edge_id) is Propagation.LAZY
    assert edge.propagation is Propagation.LAZY

    assert editor.undo() is True
    assert edge.propagation is Propagation.EAGER


def test_the_menu_toggle_refuses_below_edit(held_graph, editor, edge):
    route = edit_route(editor, LevelMode.OPERATE)

    assert _toggle_through_the_menu(held_graph, route, edge.edge_id) is Propagation.EAGER
    assert _toggle_through_the_menu(held_graph, None, edge.edge_id) is Propagation.EAGER
    assert edge.propagation is Propagation.EAGER
    assert editor.can_undo() is False


def _propagation_switch(ctx: Any) -> Any:
    """Draw the propagation panel for ``ctx``'s active edge and return its switch."""
    from haybale_graph_editor.panels.properties.introspect.edge import EdgePropagationPanel

    client = Client(cast(Any, _noop_page), request=None)
    with client:
        layout = ui.column()
        EdgePropagationPanel().draw(ctx, cast(Any, layout))
    return next(el for el in client.elements.values() if isinstance(el, ui.switch))


@pytest.mark.parametrize("mode", [LevelMode.VIEW, "locked-admin"], ids=["view", "locked-admin"])
def test_the_propagation_switch_refuses_below_edit(held_graph, editor, edge, mode):
    route = _locked_admin_route(editor) if mode == "locked-admin" else edit_route(editor, mode)
    switch = _propagation_switch(_ctx(route, active_edge=edge))

    switch.value = True

    assert edge.propagation is Propagation.EAGER
    assert switch.value is False
    assert editor.can_undo() is False


def test_the_propagation_switch_refuses_once_the_level_is_locked(held_graph, editor, edge):
    mode = [LevelMode.EDIT]
    route = EditRoute(lambda: editor, lambda: mode[0])
    switch = _propagation_switch(_ctx(route, active_edge=edge))

    mode[0] = LevelMode.VIEW
    switch.value = True

    assert edge.propagation is Propagation.EAGER
    assert switch.value is False


def test_the_propagation_switch_writes_for_edit(held_graph, editor, edge):
    switch = _propagation_switch(_ctx(edit_route(editor), active_edge=edge))

    switch.value = True

    assert edge.propagation is Propagation.LAZY
    assert editor.undo() is True
    assert edge.propagation is Propagation.EAGER
