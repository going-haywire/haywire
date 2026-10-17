"""``EditRoute``: the level-mode gate in front of the ``Editor``."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

import pytest

from haywire.core.access import LevelMode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.edit_route import EditRoute
from haywire.core.graph.editor import Editor
from haywire.core.graph.properties import GraphProperties
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.setting_owner import setting_owner
from haywire.core.graph.types import ChangeReason
from haywire.core.undo.config import UndoConfig

from tests.conftest import make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"
_ADD_SLOTS = "haybale-testing:node:AddPortTestNode"
_SETTINGS_NODE = "haybale-testing:node:SettingsNode"


def _held_graph() -> BaseGraph:
    return BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )


@pytest.fixture
def held_graph(library_system) -> Iterator[BaseGraph]:
    graph = _held_graph()
    yield graph
    graph._validation.clear()
    graph.cleanup()


@pytest.fixture
def editor(held_graph: BaseGraph, library_system) -> Editor:
    config = UndoConfig(enable_auto_grouping=False, enable_action_merging=False)
    return Editor(held_graph, library_system.get_node_factory(), undo_config=config)


class _Mode:
    """A mutable level mode the route reads at each call."""

    def __init__(self, value: LevelMode) -> None:
        self.value = value

    def __call__(self) -> LevelMode:
        return self.value


@pytest.fixture
def mode() -> _Mode:
    return _Mode(LevelMode.EDIT)


@pytest.fixture
def route(editor: Editor, mode: _Mode) -> EditRoute:
    return EditRoute(lambda: editor, mode)


def test_the_editor_is_read_at_each_call(held_graph: BaseGraph, editor: Editor, library_system, mode: _Mode):
    other_graph = _held_graph()
    try:
        other = Editor(other_graph, library_system.get_node_factory())
        current = [editor]
        route = EditRoute(lambda: current[0], mode)
        first = make_node(held_graph, _ADD)
        second = make_node(other_graph, _ADD)

        assert route.set_port(first.node_id, "value_a", 1.0, minimum=LevelMode.EDIT) is True
        current[0] = other
        assert route.graph is other_graph
        assert route.set_port(second.node_id, "value_a", 2.0, minimum=LevelMode.EDIT) is True
        assert route.set_port(first.node_id, "value_a", 3.0, minimum=LevelMode.EDIT) is False

        assert first.node.ports["value_a"].data.get_own_value() == 1.0
        assert second.node.ports["value_a"].data.get_own_value() == 2.0
    finally:
        other_graph._validation.clear()
        other_graph.cleanup()


@pytest.mark.parametrize("level", list(LevelMode))
def test_the_editor_is_handed_out_only_in_edit(
    route: EditRoute, editor: Editor, mode: _Mode, level: LevelMode
):
    mode.value = level

    assert route.editor() is (editor if level is LevelMode.EDIT else None)


def test_a_write_below_its_minimum_changes_nothing(held_graph: BaseGraph, route: EditRoute, mode: _Mode):
    mode.value = LevelMode.OPERATE
    before = held_graph.meta.label

    assert route.set_setting(held_graph.meta, "label", "Renamed", minimum=LevelMode.EDIT) is False
    assert route.reset_setting(held_graph.meta, "label", minimum=LevelMode.EDIT) is False

    assert held_graph.meta.label == before


def test_set_port_writes_and_marks(held_graph: BaseGraph, route: EditRoute):
    wrapper = make_node(held_graph, _ADD)
    held_graph._validation.force_immediate_validation()

    assert route.set_port(wrapper.node_id, "value_a", 4.0, minimum=LevelMode.OPERATE) is True

    assert wrapper.node.ports["value_a"].data.get_own_value() == 4.0
    result = held_graph._validation.force_immediate_validation()
    assert result is not None
    assert result.nodes == {wrapper.node_id: ChangeReason.NODE_VALUE_CHANGED}


def test_edit_mode_records_and_operate_does_not(
    held_graph: BaseGraph, editor: Editor, route: EditRoute, mode: _Mode
):
    wrapper = make_node(held_graph, _ADD)
    held_graph._validation.force_immediate_validation()
    port = wrapper.node.ports["value_a"]

    mode.value = LevelMode.OPERATE
    assert route.set_port(wrapper.node_id, "value_a", 4.0, minimum=LevelMode.OPERATE) is True
    assert editor.can_undo() is False

    mode.value = LevelMode.EDIT
    assert route.set_port(wrapper.node_id, "value_a", 5.0, minimum=LevelMode.OPERATE) is True
    assert editor.can_undo() is True
    editor.undo()
    assert port.data.get_own_value() == 4.0


@pytest.fixture
def merging_editor(held_graph: BaseGraph, library_system) -> Editor:
    config = UndoConfig(enable_auto_grouping=False, enable_action_merging=True)
    return Editor(held_graph, library_system.get_node_factory(), undo_config=config)


def test_two_routes_never_merge(held_graph: BaseGraph, merging_editor: Editor):
    wrapper = make_node(held_graph, _ADD)
    held_graph._validation.force_immediate_validation()
    port = wrapper.node.ports["value_a"]
    a = EditRoute(lambda: merging_editor, lambda: LevelMode.EDIT)
    b = EditRoute(lambda: merging_editor, lambda: LevelMode.EDIT)
    start = port.data.get_own_value()

    a.set_port(wrapper.node_id, "value_a", 1.0, minimum=LevelMode.OPERATE)
    b.set_port(wrapper.node_id, "value_a", 2.0, minimum=LevelMode.OPERATE)
    a.set_port(wrapper.node_id, "value_a", 3.0, minimum=LevelMode.OPERATE)

    for expected in (2.0, 1.0, start):
        assert merging_editor.undo() is True
        assert port.data.get_own_value() == expected
    assert merging_editor.can_undo() is False


def test_an_operate_write_between_edit_writes_splits_the_run(held_graph: BaseGraph, merging_editor: Editor):
    wrapper = make_node(held_graph, _ADD)
    held_graph._validation.force_immediate_validation()
    port = wrapper.node.ports["value_a"]
    edit = EditRoute(lambda: merging_editor, lambda: LevelMode.EDIT)
    operate = EditRoute(lambda: merging_editor, lambda: LevelMode.OPERATE)
    port.data.set_value(2.0)

    edit.set_port(wrapper.node_id, "value_a", 5.0, minimum=LevelMode.OPERATE)
    operate.set_port(wrapper.node_id, "value_a", 6.0, minimum=LevelMode.OPERATE)
    edit.set_port(wrapper.node_id, "value_a", 7.0, minimum=LevelMode.OPERATE)

    assert merging_editor.undo() is True
    assert port.data.get_own_value() == 6.0
    assert merging_editor.undo() is True
    assert port.data.get_own_value() == 2.0
    assert merging_editor.can_undo() is False


def test_the_mode_is_read_at_each_write(held_graph: BaseGraph, route: EditRoute, mode: _Mode):
    wrapper = make_node(held_graph, _ADD)

    assert route.set_port(wrapper.node_id, "value_a", 1.0, minimum=LevelMode.OPERATE) is True
    mode.value = LevelMode.VIEW
    assert route.set_port(wrapper.node_id, "value_a", 2.0, minimum=LevelMode.OPERATE) is False

    assert wrapper.node.ports["value_a"].data.get_own_value() == 1.0


def test_a_setting_write_and_reset_reach_the_document_bag(held_graph: BaseGraph, route: EditRoute):
    wrapper = make_node(held_graph, _SETTINGS_NODE)
    held_graph._validation.force_immediate_validation()
    bag = cast(Any, wrapper.node).example

    assert route.set_setting(bag, "persistent_value", 5.0, minimum=LevelMode.EDIT) is True
    assert bag.persistent_value == 5.0
    assert route.reset_setting(bag, "persistent_value", minimum=LevelMode.EDIT) is True
    assert bag._is_locally_set("persistent_value") is False


def test_a_bag_no_document_saves_is_written_directly(held_graph: BaseGraph, route: EditRoute):
    bag = GraphProperties()
    assert setting_owner(held_graph, bag) is None
    original = bag.open_locked

    assert route.set_setting(bag, "open_locked", not original, minimum=LevelMode.EDIT) is True
    assert bag.open_locked is (not original)
    assert route.reset_setting(bag, "open_locked", minimum=LevelMode.EDIT) is True
    assert bag._is_locally_set("open_locked") is False
    assert route.set_setting(bag, "no_such_field", 1, minimum=LevelMode.EDIT) is False


def test_a_port_without_an_own_value_is_refused(held_graph: BaseGraph, route: EditRoute):
    from haywire.barn.builtin.types import ADD

    wrapper = make_node(held_graph, _ADD_SLOTS)
    port = wrapper.node.ports.get("add_in_0")
    assert port is not None
    assert port.type_cls is not None
    assert issubclass(port.type_cls, ADD)

    assert route.set_port(wrapper.node_id, "add_in_0", 1.0, minimum=LevelMode.OPERATE) is False


def test_a_non_operable_port_is_refused_in_operate(held_graph: BaseGraph, route: EditRoute, mode: _Mode):
    from haywire.barn.builtin.types import FLOAT
    from haywire.barn.builtin.widget_keys import NUMBER_WIDGET

    wrapper = make_node(held_graph, _ADD)
    wrapper.node.add(FLOAT.as_config("gain", default=1.0, operable=False, widget_key=NUMBER_WIDGET))
    port = wrapper.node.ports["gain"]
    assert port.operable is False

    mode.value = LevelMode.OPERATE
    assert route.set_port(wrapper.node_id, "gain", 2.0, minimum=LevelMode.OPERATE) is False
    assert port.data.get_own_value() == 1.0

    mode.value = LevelMode.EDIT
    assert route.set_port(wrapper.node_id, "gain", 2.0, minimum=LevelMode.OPERATE) is True
    assert port.data.get_own_value() == 2.0


def test_a_non_operable_setting_is_refused_in_operate(
    held_graph: BaseGraph, route: EditRoute, mode: _Mode, monkeypatch: pytest.MonkeyPatch
):
    wrapper = make_node(held_graph, _SETTINGS_NODE)
    bag = cast(Any, wrapper.node).example
    descriptor = type(bag)._settings_descriptors()["persistent_value"]
    monkeypatch.setattr(descriptor, "_operable", False)
    before = bag.persistent_value

    mode.value = LevelMode.OPERATE
    assert route.set_setting(bag, "persistent_value", 7.0, minimum=LevelMode.OPERATE) is False
    assert route.reset_setting(bag, "persistent_value", minimum=LevelMode.OPERATE) is False
    assert bag.persistent_value == before

    mode.value = LevelMode.EDIT
    assert route.set_setting(bag, "persistent_value", 7.0, minimum=LevelMode.OPERATE) is True
    assert bag.persistent_value == 7.0


def test_an_operable_target_keeps_its_minimum(held_graph: BaseGraph, route: EditRoute, mode: _Mode):
    wrapper = make_node(held_graph, _ADD)
    assert wrapper.node.ports["value_a"].operable is True

    mode.value = LevelMode.OPERATE
    assert route.set_port(wrapper.node_id, "value_a", 3.0, minimum=LevelMode.OPERATE) is True


def test_the_annotation_text_needs_edit(
    held_graph: BaseGraph, editor: Editor, route: EditRoute, mode: _Mode
):
    from haywire.barn.builtin.nodes.annotation import AnnotationNode

    wrapper = make_node(held_graph, AnnotationNode.class_identity.registry_key)
    held_graph._validation.force_immediate_validation()
    bag = cast(Any, wrapper.node).annotation

    mode.value = LevelMode.OPERATE
    assert route.set_setting(bag, "text", "Hello", minimum=LevelMode.OPERATE) is False
    assert bag.text == ""

    mode.value = LevelMode.EDIT
    assert route.set_setting(bag, "text", "Hello", minimum=LevelMode.OPERATE) is True
    assert bag.text == "Hello"
    result = held_graph._validation.force_immediate_validation()
    assert result is not None
    assert result.graph is ChangeReason.GRAPH_CONTENT_CHANGED
    assert editor.can_undo() is True
    editor.undo()
    assert bag.text == ""


def test_a_setting_reached_through_set_port_keeps_its_operable_rule(
    held_graph: BaseGraph, route: EditRoute, mode: _Mode
):
    """``Editor.set_property`` resolves a name that is no port as a settings field."""
    from haywire.barn.builtin.nodes.annotation import AnnotationNode

    wrapper = make_node(held_graph, AnnotationNode.class_identity.registry_key)
    mode.value = LevelMode.OPERATE

    assert route.set_port(wrapper.node_id, "text", "Sneaked", minimum=LevelMode.OPERATE) is False
    assert cast(Any, wrapper.node).annotation.text == ""
