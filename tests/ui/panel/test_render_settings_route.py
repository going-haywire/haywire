"""A settings form drawn with an edit route writes through it, and refuses below level mode edit.

The route's level mode is read at every write, so a row drawn in any mode
refuses once the mode is below edit. A row's write marks the graph unsaved
only when it changed what the field stores.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast
from unittest.mock import patch

import pytest
from nicegui import Client, ui

from haywire.barn.builtin.types import FLOAT, INT, OPTIONAL
from haywire.core.access import LevelMode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.edit_route import EditRoute
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.types import ChangeReason
from haywire.core.settings import Settings, setting
from haywire.core.undo.config import UndoConfig
from haywire.ui.panel import render_utils
from haywire.ui.panel.render_utils import render_settings

from tests.conftest import make_node
from tests.ui.panel.render_ctx import make_render_ctx

pytestmark = pytest.mark.integration

_SETTINGS_NODE = "haybale-testing:node:SettingsNode"


def _noop_page() -> None:  # registration target for a headless Client
    pass


class _GateSettings(Settings):
    gain = setting[FLOAT](1.0, label="Gain")
    count = setting[OPTIONAL[INT]](3, label="Count")


class _Level:
    """A level whose mode a test flips, and the route over its editor."""

    def __init__(self, editor: Editor, mode: LevelMode = LevelMode.EDIT) -> None:
        self.mode = mode
        self.route = EditRoute(lambda: editor, lambda: self.mode)


@pytest.fixture
def held_graph(library_system) -> Iterator[BaseGraph]:
    """A graph whose debounce never fires on its own, so a test drains it explicitly."""
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    yield graph
    graph._validation.clear()
    graph.cleanup()


@pytest.fixture
def level(held_graph: BaseGraph, library_system) -> _Level:
    config = UndoConfig(enable_auto_grouping=False, enable_action_merging=False)
    return _Level(Editor(held_graph, library_system.get_node_factory(), undo_config=config))


@pytest.fixture
def node_bag(held_graph: BaseGraph) -> Any:
    """The ``example`` bag of a ``SettingsNode`` in ``held_graph``, with every mark drained."""
    wrapper = make_node(held_graph, _SETTINGS_NODE)
    _drain(held_graph)
    return cast(Any, wrapper.node).example


def _drain(graph: BaseGraph):
    return graph._validation.force_immediate_validation()


def _drain_graph_marks(graph: BaseGraph):
    """Run the batch the debounce would: ``force_immediate_validation`` skips a graph-only mark."""
    return graph._validation._validate_batch()


def _marks_the_node(graph: BaseGraph, bag: Any) -> bool:
    result = _drain(graph)
    if result is None:
        return False
    assert result.nodes == {bag._node.node_id: ChangeReason.NODE_VALUE_CHANGED}
    return True


def _walk(element):
    yield element
    for child in element.default_slot.children:
        yield from _walk(child)


def _walk_skip_menus(element):
    yield element
    if type(element).__name__ == "ContextMenu":
        return
    for child in element.default_slot.children:
        yield from _walk_skip_menus(child)


def _find_field_row(root, attr_name: str):
    for el in _walk(root):
        if getattr(el, "_props", {}).get("data-field") == attr_name:
            return el
    return None


def _widget_is_disabled(row) -> bool:
    for el in _walk_skip_menus(row):
        if getattr(el, "_props", {}).get("disable") is True:
            return True
        style = getattr(el, "_style", {}) or {}
        if style.get("opacity") == "0.5" and style.get("pointer-events") == "none":
            return True
    return False


def _menu_item_text(item) -> str:
    for child in item.default_slot.children:
        text = getattr(child, "text", None)
        if text is not None:
            return text
    return ""


def _menu_items(row) -> dict[str, Any]:
    return {_menu_item_text(el): el for el in _walk(row) if type(el).__name__ == "MenuItem"}


def _render(bag, route: EditRoute | None) -> tuple[Any, dict[str, Any]]:
    """Render *bag* with *route*; return the anchor and each row's ``on_edit``, by field name."""
    on_edits: dict[str, Any] = {}
    real = render_utils._resolve_widget_instance

    def _capture(defn, on_edit, **kwargs):
        on_edits[defn._attr_name] = on_edit
        return real(defn, on_edit, **kwargs)

    client = Client(cast(Any, _noop_page), request=None)
    with client, patch.object(render_utils, "_resolve_widget_instance", _capture):
        anchor = ui.column()
        with anchor:
            render_settings(make_render_ctx(), bag, route=route)
    return anchor, on_edits


def _render_with_float_widget(bag, route: EditRoute, attr_name: str) -> Any:
    """Render *bag* with *route*, drawing *attr_name*'s row with a real float widget; return it."""
    from haywire.ui.widget import globals as widget_globals

    from tests.ui.widget._sync_fixtures import _BaseDefaultFloatWidget

    widgets: list[Any] = []
    real_resolve = render_utils._resolve_widget_instance

    def _recording(model):
        widgets.append(_BaseDefaultFloatWidget(model))
        return widgets[-1]

    def _resolve(defn, on_edit, **kwargs):
        if defn._attr_name != attr_name:
            return real_resolve(defn, on_edit, **kwargs)
        with patch.object(widget_globals, "get_widget_class", lambda _key: _recording):
            return real_resolve(defn, on_edit, **kwargs)

    client = Client(cast(Any, _noop_page), request=None)
    with client, patch.object(render_utils, "_resolve_widget_instance", _resolve):
        with ui.column():
            render_settings(make_render_ctx(), bag, route=route)
    assert len(widgets) == 1
    return widgets[0]


def _click(item) -> None:
    """Fire a NiceGUI element's registered click handler headlessly."""
    listener_id = next(iter(item._event_listeners))
    item._handle_event({"listener_id": listener_id, "args": {}})


# =============================================================================
# Below level mode edit, a write is refused
# =============================================================================


def test_a_refused_row_write_snaps_back(level: _Level, held_graph: BaseGraph, node_bag: Any):
    level.mode = LevelMode.OPERATE
    widget = _render_with_float_widget(node_bag, level.route, "persistent_value")

    widget.el.value = 5.0
    widget._bindings[0]._sync_to_model(5.0)

    assert node_bag.persistent_value == 1.0
    assert widget.el.value == 1.0
    assert not _marks_the_node(held_graph, node_bag)


def test_rows_render_enabled_when_allowed(level: _Level):
    anchor, _ = _render(_GateSettings(), level.route)

    assert not _widget_is_disabled(_find_field_row(anchor, "gain"))


def test_a_stale_row_refuses_at_write_time(level: _Level, held_graph: BaseGraph, node_bag: Any):
    _anchor, on_edits = _render(node_bag, level.route)

    level.mode = LevelMode.OPERATE
    on_edits["persistent_value"](5.0)

    assert node_bag.persistent_value == 1.0
    assert not _marks_the_node(held_graph, node_bag)


def test_a_row_drawn_before_the_lock_refuses_its_widgets_edit_and_shows_the_model(
    level: _Level, held_graph: BaseGraph, node_bag: Any
):
    widget = _render_with_float_widget(node_bag, level.route, "persistent_value")

    level.mode = LevelMode.OPERATE
    widget.el.value = 5.0
    widget._bindings[0]._sync_to_model(5.0)

    assert node_bag.persistent_value == 1.0
    assert widget.el.value == 1.0
    assert not _marks_the_node(held_graph, node_bag)


def test_a_refused_reset_leaves_the_value(level: _Level, held_graph: BaseGraph, node_bag: Any):
    node_bag.persistent_value = 4.0
    _drain(held_graph)
    anchor, _ = _render(node_bag, level.route)
    reset = _menu_items(_find_field_row(anchor, "persistent_value"))["Reset to default"]

    level.mode = LevelMode.OPERATE
    _click(reset)

    assert node_bag.persistent_value == 4.0
    assert not _marks_the_node(held_graph, node_bag)


def test_a_refused_set_to_none_leaves_the_value(level: _Level):
    bag = _GateSettings()
    anchor, _ = _render(bag, level.route)

    level.mode = LevelMode.OPERATE
    _click(_menu_items(_find_field_row(anchor, "count"))["Set to none"])

    assert bag.count == 3


# =============================================================================
# A write that lands marks the node only when it changed what the field stores
# =============================================================================


def test_a_rows_edit_marks_the_node(level: _Level, held_graph: BaseGraph, node_bag: Any):
    _anchor, on_edits = _render(node_bag, level.route)

    on_edits["persistent_value"](5.0)

    assert node_bag.persistent_value == 5.0
    assert _marks_the_node(held_graph, node_bag)


def test_a_row_widgets_edit_lands_while_the_mode_allows(level: _Level, held_graph: BaseGraph, node_bag: Any):
    widget = _render_with_float_widget(node_bag, level.route, "persistent_value")

    widget.el.value = 5.0
    widget._bindings[0]._sync_to_model(5.0)

    assert node_bag.persistent_value == 5.0
    assert _marks_the_node(held_graph, node_bag)


def test_a_row_widget_echoing_the_current_value_is_not_written(
    level: _Level, held_graph: BaseGraph, node_bag: Any
):
    widget = _render_with_float_widget(node_bag, level.route, "persistent_value")

    widget._bindings[0]._sync_to_model(1.0)

    assert not _marks_the_node(held_graph, node_bag)


def test_an_edit_to_the_current_value_is_not_written(level: _Level, held_graph: BaseGraph, node_bag: Any):
    _anchor, on_edits = _render(node_bag, level.route)

    on_edits["persistent_value"](1.0)

    assert not _marks_the_node(held_graph, node_bag)


def test_set_to_none_on_an_absent_value_is_not_written(level: _Level, held_graph: BaseGraph, node_bag: Any):
    anchor, _ = _render(node_bag, level.route)

    _click(_menu_items(_find_field_row(anchor, "optional_int"))["Set to none"])

    assert node_bag.optional_int is None
    assert not _marks_the_node(held_graph, node_bag)


def test_set_to_none_on_a_value_is_written(level: _Level, held_graph: BaseGraph, node_bag: Any):
    anchor, _ = _render(node_bag, level.route)

    _click(_menu_items(_find_field_row(anchor, "optional_with_default"))["Set to none"])

    assert node_bag.optional_with_default is None
    assert _marks_the_node(held_graph, node_bag)


def test_resetting_a_field_with_no_local_value_is_not_written(
    level: _Level, held_graph: BaseGraph, node_bag: Any
):
    anchor, _ = _render(node_bag, level.route)

    _click(_menu_items(_find_field_row(anchor, "persistent_value"))["Reset to default"])

    assert node_bag.persistent_value == 1.0
    assert not _marks_the_node(held_graph, node_bag)


def test_resetting_a_local_value_equal_to_the_default_is_written(
    level: _Level, held_graph: BaseGraph, node_bag: Any
):
    node_bag.persistent_value = 4.0
    node_bag.persistent_value = 1.0
    _drain(held_graph)
    anchor, _ = _render(node_bag, level.route)

    _click(_menu_items(_find_field_row(anchor, "persistent_value"))["Reset to default"])

    assert node_bag._is_locally_set("persistent_value") is False
    assert _marks_the_node(held_graph, node_bag)


def test_an_accepted_reset_is_written(level: _Level, held_graph: BaseGraph, node_bag: Any):
    node_bag.persistent_value = 4.0
    _drain(held_graph)
    anchor, _ = _render(node_bag, level.route)

    _click(_menu_items(_find_field_row(anchor, "persistent_value"))["Reset to default"])

    assert node_bag.persistent_value == 1.0
    assert _marks_the_node(held_graph, node_bag)


def test_a_graph_props_row_marks_the_graph_unsaved(level: _Level, held_graph: BaseGraph):
    _drain_graph_marks(held_graph)
    _anchor, on_edits = _render(held_graph.props, level.route)

    on_edits["open_locked"](not held_graph.props.open_locked)

    result = _drain_graph_marks(held_graph)
    assert result is not None
    assert result.graph is ChangeReason.GRAPH_CONTENT_CHANGED
    assert result.requires_save()


def test_a_rejected_value_shows_the_error_and_marks_nothing(
    level: _Level, held_graph: BaseGraph, node_bag: Any
):
    anchor, on_edits = _render(node_bag, level.route)

    on_edits["even_int"](7)

    errors = [el for el in _walk(anchor) if getattr(el, "_props", {}).get("data-error") == "true"]
    assert [el.text for el in errors] == ["Invalid value: 7"]
    assert node_bag.even_int == 4
    assert _drain(held_graph) is None


# =============================================================================
# Without a route
# =============================================================================


def test_without_a_route_rows_write_the_bag_directly():
    bag = _GateSettings()
    anchor, on_edits = _render(bag, None)

    assert not _widget_is_disabled(_find_field_row(anchor, "gain"))
    on_edits["gain"](5.0)
    assert bag.gain == 5.0
    _click(_menu_items(_find_field_row(anchor, "gain"))["Reset to default"])
    assert bag._is_locally_set("gain") is False


def test_without_a_route_rows_offer_no_promotion(held_graph: BaseGraph, node_bag: Any):
    anchor, _ = _render(node_bag, None)

    assert "Promote to" not in _menu_items(_find_field_row(anchor, "persistent_value"))


# =============================================================================
# Promotion is a structure edit: it needs the route's editor
# =============================================================================


def _port_id(bag: Any) -> str:
    """The id of the port ``persistent_value`` promotes to."""
    return type(bag)._settings_descriptors()["persistent_value"].storage_key


def _promote_item(anchor, attr_name: str) -> Any:
    items = _menu_items(_find_field_row(anchor, attr_name))
    assert "Promote to" in items
    return items["inlet"]


def test_promotion_needs_the_routes_editor(level: _Level, node_bag: Any):
    level.mode = LevelMode.OPERATE
    anchor, _ = _render(node_bag, level.route)
    inlet = _promote_item(anchor, "persistent_value")

    _click(inlet)

    assert _port_id(node_bag) not in node_bag._node.ports


def test_promotion_with_an_edit_route_adds_the_port(level: _Level, node_bag: Any):
    anchor, _ = _render(node_bag, level.route)

    _click(_promote_item(anchor, "persistent_value"))

    assert _port_id(node_bag) in node_bag._node.ports


def test_a_stale_promotion_entry_refuses_once_the_mode_drops(level: _Level, node_bag: Any):
    anchor, _ = _render(node_bag, level.route)
    inlet = _promote_item(anchor, "persistent_value")

    level.mode = LevelMode.OPERATE
    _click(inlet)

    assert _port_id(node_bag) not in node_bag._node.ports
