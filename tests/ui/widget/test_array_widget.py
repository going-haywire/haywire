"""ArrayWidget — a list editor that draws each item with the item type's own widget.

Delegation is the design, as for ``OptionalWidget``: the widget never names an
item type. It reads the item type off the cell and builds that type's declared
widget once per item. ``STRING``, ``INT`` and ``FLOAT`` are the tested item
types. The browser half is in ``tests/ui/harness/test_list_widget.py``.
"""

from typing import Any, cast

import pytest
from nicegui import Client

from haybale_core.types import ArrayType
from haybale_core.widgets.array_widget import ArrayWidget
from haywire.barn.builtin import widgets as builtin_widgets
from haywire.barn.builtin.types import FLOAT, INT, STRING
from haywire.barn.builtin.widgets import NumberWidget, TextWidget
from haywire.ui.panel.setting_widget_model import SettingWidgetModel
from haywire.ui.widget.globals import WIDGET_REGISTRY

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


@pytest.fixture(autouse=True)
def registered_widgets():
    """Publish the builtin widgets and ArrayWidget as a library load would; restore after."""
    before = dict(WIDGET_REGISTRY)
    for name in builtin_widgets.__all__:
        cls = getattr(builtin_widgets, name)
        WIDGET_REGISTRY[cls.class_identity.registry_key] = cls
    WIDGET_REGISTRY[ArrayWidget.class_identity.registry_key] = ArrayWidget
    yield
    WIDGET_REGISTRY.clear()
    WIDGET_REGISTRY.update(before)


def _rendered(item_cls, initial, widget_config=None, on_edit=None):
    """An ArrayWidget on an ``ArrayType[item_cls]`` cell.

    Returns ``(widget, cell, edits)``. The default ``on_edit`` records each
    write and lands it in the cell.
    """
    array: Any = ArrayType
    cell = array[item_cls].create_field(default_override={"value": list(initial)})
    edits: list = []

    def write(value: Any) -> None:
        edits.append(value)
        cell.set_value(value)

    model = SettingWidgetModel(
        field_id="items",
        widget_config=widget_config or {"properties": {}},
        cell=cell,
        on_edit=on_edit or write,
    )
    widget = ArrayWidget(model)
    with Client(cast(Any, _noop_page), request=None):
        widget.render()
    return cast(Any, widget), cell, edits


def _in_client(widget: Any, action) -> None:
    """Run *action* in the widget's client, since a row rebuild creates elements."""
    with widget.ui_element.client:
        action()


@pytest.mark.parametrize(
    ("item_cls", "initial", "expected"),
    [(STRING, ["a", "b"], TextWidget), (INT, [1, 2, 3], NumberWidget), (FLOAT, [0.5], NumberWidget)],
)
def test_each_item_gets_its_type_widget(item_cls, initial, expected):
    widget, _, _ = _rendered(item_cls, initial)
    assert len(widget._rows) == len(initial)
    assert all(type(row) is expected for row in widget._rows)


def test_an_int_row_steps_in_whole_numbers():
    widget, _, _ = _rendered(INT, [1])
    drag = widget._rows[0].ui_element
    assert drag._props["precision"] == 0
    assert drag._props["step"] == 1


def test_a_row_edit_writes_a_new_list():
    widget, cell, _ = _rendered(STRING, ["a", "b"])
    before = cell.get_value()
    widget._rows[1].port.set_value("B")
    after = cell.get_value()
    assert after == ["a", "B"]
    assert after is not before


def test_an_int_row_stores_ints():
    widget, cell, _ = _rendered(INT, [1, 2])
    widget._rows[0].port.set_value(4.0)
    assert cell.get_value() == [4, 2]
    assert type(cell.get_value()[0]) is int


@pytest.mark.parametrize(("item_cls", "default"), [(STRING, ""), (INT, 0), (FLOAT, 0.0)])
def test_add_appends_the_item_default(item_cls, default):
    initials: dict[Any, list[Any]] = {STRING: ["a"], INT: [1], FLOAT: [1.5]}
    initial = initials[item_cls]
    widget, cell, _ = _rendered(item_cls, initial)
    _in_client(widget, widget._add)
    assert cell.get_value() == [*initial, default]
    assert type(cell.get_value()[-1]) is type(default)
    assert len(widget._rows) == len(initial) + 1


def test_remove():
    widget, cell, _ = _rendered(STRING, ["a", "b", "c"])
    _in_client(widget, lambda: widget._remove(1))
    assert cell.get_value() == ["a", "c"]


def test_a_drop_moves_one_item_and_rebuilds_the_rows():
    # SortableJS has already moved the dragged row in the DOM, and every row
    # widget reads a fixed index, so the rows are rebuilt to match the new list.
    widget, cell, _ = _rendered(STRING, ["a", "b", "c"])
    old_rows = list(widget._rows)
    _in_client(widget, lambda: widget._reorder(0, 2))
    assert cell.get_value() == ["b", "c", "a"]
    assert [row._input.value for row in widget._rows] == ["b", "c", "a"]
    assert all(row._cleaned_up for row in old_rows)


def test_a_drop_in_place_writes_nothing():
    widget, _, edits = _rendered(STRING, ["a", "b"])
    _in_client(widget, lambda: widget._reorder(1, 1))
    _in_client(widget, lambda: widget._reorder(0, 5))
    assert edits == []


def test_a_refused_drop_redraws_the_model_order():
    widget, cell, _ = _rendered(STRING, ["a", "b"], on_edit=lambda _value: False)
    old_rows = list(widget._rows)
    _in_client(widget, lambda: widget._reorder(0, 1))
    assert cell.get_value() == ["a", "b"]
    assert [row._input.value for row in widget._rows] == ["a", "b"]
    assert widget._rows != old_rows, "the DOM order the drop left behind is redrawn"


def test_each_row_has_a_grip_the_canvas_leaves_alone():
    widget, _, _ = _rendered(STRING, ["a", "b", "c"])
    assert len(widget._grips) == 3
    for grip in widget._grips:
        assert "hw-array-grip" in grip.classes
        assert "drag-handle" not in grip.classes, "canvas.vue drags the node by .drag-handle"
        assert grip.props["data-interactive"] == "true"
    assert widget._rows_box._sortable is not None


def test_an_external_shrink_rebuilds_rows_without_error():
    # Outside any client context, as a reset or undo from another handler arrives.
    widget, cell, _ = _rendered(STRING, ["a", "b", "c"])
    cell.set_value(["x"])
    assert len(widget._rows) == 1
    assert widget._rows[0]._input.value == "x"


def test_two_widgets_on_one_list_both_follow_a_count_change():
    # The panel and the card can show the same list; one rebuilding must not
    # make the cell skip the other's update.
    first, cell, _ = _rendered(STRING, ["a", "b"])
    second = cast(Any, ArrayWidget(first.port))
    with Client(cast(Any, _noop_page), request=None):
        second.render()
    _in_client(first, first._add)
    assert len(first._rows) == 3
    assert len(second._rows) == 3
    cell.set_value(["z"])
    assert len(first._rows) == len(second._rows) == 1


def test_an_edit_keeps_the_rows():
    widget, _, _ = _rendered(STRING, ["a", "b"])
    rows = list(widget._rows)
    widget._rows[0].port.set_value("z")
    assert widget._rows == rows
    assert widget._rows[0]._input.value == "z"


def test_a_rebuild_releases_old_rows():
    widget, cell, _ = _rendered(STRING, ["a", "b"])
    baseline = cell.on_changed.handler_size
    old_rows = list(widget._rows)
    _in_client(widget, widget._add)
    _in_client(widget, lambda: widget._remove(0))
    assert cell.on_changed.handler_size == baseline
    assert all(row._cleaned_up for row in old_rows)


def test_a_refused_add_redraws_the_model():
    widget, cell, _ = _rendered(STRING, ["a"], on_edit=lambda _value: False)
    _in_client(widget, widget._add)
    assert cell.get_value() == ["a"]
    assert len(widget._rows) == 1


def test_item_config_reaches_every_row():
    config = {"properties": {"item": {"commit": True}}}
    widget, _, _ = _rendered(STRING, ["a", "b"], widget_config=config)
    assert all(row._config["properties"]["commit"] is True for row in widget._rows)


def test_an_item_type_without_a_widget_shows_a_summary():
    del WIDGET_REGISTRY[TextWidget.class_identity.registry_key]
    widget, _, _ = _rendered(STRING, ["a", "b"])
    assert widget._rows == []
    assert widget._add_button is None
    assert widget._summary.text == "2 items"


def test_a_linked_list_refuses_every_edit(graph_with_library_system):
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    graph = graph_with_library_system
    src = graph.create_node_wrapper("haybale-testing:node:SettingsNode", position=(0, 0))
    sink = graph.create_node_wrapper("haybale-testing:node:SettingsNode", position=(200, 0))
    for wrapper, direction in ((src, PortType.OUTLET), (sink, PortType.INLET)):
        promote_setting(wrapper.node, "example", "example_string_list", direction=direction)
    pid = type(sink.node.example).__dict__["example_string_list"].storage_key
    assert graph.create_edge_wrapper(src.node_id, pid, sink.node_id, pid) is not None

    src.node.example.example_string_list = ["L1", "L2"]
    sink_port = sink.node.ports[pid]
    sink_port.resolve_dirty_data()
    assert sink_port.get_value() == ["L1", "L2"]

    widget = cast(Any, ArrayWidget(sink_port))
    with Client(cast(Any, _noop_page), request=None):
        widget.render()
        widget._rows[0].set_value("edited")
        widget._add()
        widget._remove(0)
        widget._reorder(0, 1)

    assert sink_port.get_value() == ["L1", "L2"]
    assert sink.node.example._cell_for(
        type(sink.node.example).__dict__["example_string_list"]
    ).get_own_value() == [
        "One",
        "Two",
        "Three",
    ]
