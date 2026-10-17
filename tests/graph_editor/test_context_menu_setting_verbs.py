"""The pin and selection menus' setting verbs reach the level's ``Editor`` through its edit route.

Each verb writes a saved setting, so it marks the node unsaved when the stored
value changes, and a level below edit refuses it and changes nothing.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast

import pytest

from haybale_graph_editor.editors.graph_canvas.handlers.context_menu import SessionContextMenuProvider
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.access import LevelMode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.edit_route import EditRoute
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.node.promotion import promote_setting
from haywire.core.types.enums import PortType

from tests.conftest import edit_route, make_node

pytestmark = pytest.mark.integration

_SETTINGS_NODE = "haybale-testing:node:SettingsNode"


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


@pytest.fixture
def wrapper(held_graph: BaseGraph) -> Any:
    wrapper = make_node(held_graph, _SETTINGS_NODE)
    held_graph._validation.force_immediate_validation()
    return wrapper


def _provider(graph: BaseGraph, route: EditRoute | None, wrapper: Any) -> SessionContextMenuProvider:
    """A provider over ``graph`` with ``wrapper`` right-clicked and selected."""
    edit = SimpleNamespace(
        active_route=route,
        active_graph=graph,
        active_node=wrapper,
        selected_nodes={wrapper.node_id},
    )
    provider = object.__new__(SessionContextMenuProvider)
    cast(Any, provider)._context = SimpleNamespace(data={EditState: edit})
    cast(Any, provider)._emit = lambda event: None
    return provider


def _marked(graph: BaseGraph, node_id: str) -> bool:
    """Whether the drained batch names ``node_id`` and a save would record it.

    A card field (``collapsed``, ``detail``) reports the node as a redraw, which
    outranks its value reason; the batch still requires a save.
    """
    result = graph._validation.force_immediate_validation()
    return result is not None and node_id in result.nodes and result.requires_save()


def _promoted(wrapper: Any, field: str) -> str:
    node = wrapper.node
    promote_setting(node, "example", field, PortType.INLET)
    return type(node.example).__dict__[field].storage_key


# =============================================================================
# Pin menu: reset and clear
# =============================================================================


def test_pin_reset_resets_the_setting_and_marks_the_node(held_graph, editor, wrapper):
    port_id = _promoted(wrapper, "optional_with_default")
    wrapper.node.example.optional_with_default = 7
    held_graph._validation.force_immediate_validation()

    _provider(held_graph, edit_route(editor), wrapper).reset_setting(port_id)

    assert wrapper.node.example.optional_with_default == -1
    assert wrapper.node.example._is_locally_set("optional_with_default") is False
    assert _marked(held_graph, wrapper.node_id)


def test_pin_clear_sets_absence_and_marks_the_node(held_graph, editor, wrapper):
    port_id = _promoted(wrapper, "optional_with_default")
    held_graph._validation.force_immediate_validation()

    _provider(held_graph, edit_route(editor), wrapper).clear_setting(port_id)

    assert wrapper.node.example.optional_with_default is None
    assert _marked(held_graph, wrapper.node_id)


@pytest.mark.parametrize("route_mode", [LevelMode.OPERATE, None], ids=["operate", "no-route"])
def test_pin_reset_and_clear_refuse_below_edit(held_graph, editor, wrapper, route_mode):
    port_id = _promoted(wrapper, "optional_with_default")
    wrapper.node.example.optional_with_default = 7
    held_graph._validation.force_immediate_validation()
    route = edit_route(editor, route_mode) if route_mode is not None else None
    provider = _provider(held_graph, route, wrapper)

    provider.reset_setting(port_id)
    provider.clear_setting(port_id)

    assert wrapper.node.example.optional_with_default == 7
    assert not _marked(held_graph, wrapper.node_id)


# =============================================================================
# Selection menu: collapsed and detail
# =============================================================================


def test_selection_collapse_and_detail_write_and_mark(held_graph, editor, wrapper):
    provider = _provider(held_graph, edit_route(editor), wrapper)
    props = wrapper.node.props

    provider.set_selection_collapsed(not props.collapsed)
    provider.set_selection_detail("compact")

    assert props.collapsed is True
    assert props.detail == "compact"
    assert _marked(held_graph, wrapper.node_id)


def test_selection_collapse_and_detail_refuse_below_edit(held_graph, editor, wrapper):
    provider = _provider(held_graph, edit_route(editor, LevelMode.OPERATE), wrapper)
    props = wrapper.node.props
    detail = props.detail

    provider.set_selection_collapsed(True)
    provider.set_selection_detail("compact")

    assert props.collapsed is False
    assert props.detail == detail
    assert not _marked(held_graph, wrapper.node_id)


def _multi_provider(graph: BaseGraph, route: EditRoute, wrappers: list[Any]) -> SessionContextMenuProvider:
    """A provider whose selection is every one of ``wrappers``."""
    provider = _provider(graph, route, wrappers[0])
    edit = cast(Any, provider)._context.data[EditState]
    edit.selected_nodes = {w.node_id for w in wrappers}
    return provider


def test_folding_a_multi_selection_is_one_undo_step(held_graph, editor, wrapper):
    wrappers = [wrapper, make_node(held_graph, _SETTINGS_NODE), make_node(held_graph, _SETTINGS_NODE)]
    held_graph._validation.force_immediate_validation()

    _multi_provider(held_graph, edit_route(editor), wrappers).set_selection_collapsed(True)

    assert all(w.node.props.collapsed is True for w in wrappers)
    assert editor.undo() is True
    assert all(w.node.props.collapsed is False for w in wrappers)


def test_detail_on_a_multi_selection_is_one_undo_step(held_graph, editor, wrapper):
    wrappers = [wrapper, make_node(held_graph, _SETTINGS_NODE), make_node(held_graph, _SETTINGS_NODE)]
    held_graph._validation.force_immediate_validation()
    provider = _multi_provider(held_graph, edit_route(editor), wrappers)
    provider.set_selection_detail("compact")
    assert all(w.node.props.detail == "compact" for w in wrappers)

    assert editor.undo() is True
    assert not any(w.node.props._is_locally_set("detail") for w in wrappers)


def test_clearing_every_override_is_one_undo_step_and_counts_the_nodes(held_graph, editor, wrapper):
    wrappers = [wrapper, make_node(held_graph, _SETTINGS_NODE), make_node(held_graph, _SETTINGS_NODE)]
    for w in wrappers[:2]:
        w.node.props.detail = "compact"
    held_graph._validation.force_immediate_validation()

    cleared = _multi_provider(held_graph, edit_route(editor), wrappers).clear_node_card_overrides()

    assert cleared == 2
    assert not any(w.node.props._is_locally_set("detail") for w in wrappers)
    assert editor.undo() is True
    assert all(w.node.props.detail == "compact" for w in wrappers[:2])


# =============================================================================
# Clear overrides: graph-wide and selection
# =============================================================================


@pytest.mark.parametrize("verb", ["clear_node_card_overrides", "clear_selection_detail_overrides"])
def test_clearing_detail_overrides_resets_and_marks(held_graph, editor, wrapper, verb):
    wrapper.node.props.detail = "compact"
    held_graph._validation.force_immediate_validation()

    getattr(_provider(held_graph, edit_route(editor), wrapper), verb)()

    assert wrapper.node.props._is_locally_set("detail") is False
    assert _marked(held_graph, wrapper.node_id)


@pytest.mark.parametrize("verb", ["clear_node_card_overrides", "clear_selection_detail_overrides"])
def test_clearing_detail_overrides_refuses_below_edit(held_graph, editor, wrapper, verb):
    wrapper.node.props.detail = "compact"
    held_graph._validation.force_immediate_validation()

    result = getattr(_provider(held_graph, edit_route(editor, LevelMode.OPERATE), wrapper), verb)()

    assert wrapper.node.props._is_locally_set("detail") is True
    assert wrapper.node.props.detail == "compact"
    assert not _marked(held_graph, wrapper.node_id)
    if verb == "clear_node_card_overrides":
        assert result == 0
