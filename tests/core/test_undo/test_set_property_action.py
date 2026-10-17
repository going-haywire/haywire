"""SetPropertyAction: undoable set of a port value or settings-bag field by (node_id, name)."""

import pytest

pytestmark = pytest.mark.integration  # needs library_system for builtin types/nodes

# A node with plain data inlets (example:node:MathOP has FLOAT inlets value_a/value_b).
PORT_NODE_KEY = "haybale-example:node:MathOP"
# A node carrying a settings bag (testing:node:SettingsNode -> bag 'example').
SETTINGS_NODE_KEY = "haybale-testing:node:SettingsNode"


@pytest.fixture
def graph_and_editor(library_system):
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.editor import Editor
    from haywire.core.graph.scheduler import SyncScheduler
    from haywire.core.undo.config import UndoConfig

    graph = BaseGraph("g", validation_scheduler=SyncScheduler())
    # Disable auto-grouping/merging so each operation flushes to history
    # immediately and is independently undoable — the same "one call = one undo
    # gesture" invariant the Farmhand tools get by calling ctx.fence(editor)
    # before each mutation.
    config = UndoConfig(enable_auto_grouping=False, enable_action_merging=False)
    editor = Editor(graph, library_system.get_node_factory(), undo_config=config)
    yield graph, editor
    graph.cleanup()


def _add_node(editor, registry_key=PORT_NODE_KEY):
    wrapper = editor.create_wrapper(registry_key)
    assert wrapper is not None
    return wrapper


def test_set_port_value_and_undo_redo(graph_and_editor):
    graph, editor = graph_and_editor
    wrapper = _add_node(editor)
    node = wrapper.node
    port_id = next(pid for pid, p in node.ports.items() if p.is_inlet())
    before = node.ports[port_id].get_value()

    assert editor.set_property(wrapper.node_id, port_id, 42.0) is True
    assert node.ports[port_id].get_value() == 42.0

    assert editor.undo() is True
    assert node.ports[port_id].get_value() == before

    assert editor.redo() is True
    assert node.ports[port_id].get_value() == 42.0


def test_set_settings_field_and_undo(graph_and_editor):
    graph, editor = graph_and_editor
    wrapper = _add_node(editor, SETTINGS_NODE_KEY)
    bag = wrapper.node.example
    before = bag.persistent_value
    new_value = before + 1

    assert editor.set_property(wrapper.node_id, "persistent_value", new_value) is True
    assert bag.persistent_value == new_value

    assert editor.undo() is True
    assert bag.persistent_value == before


def test_prefer_setting_beats_port_name_collision(graph_and_editor):
    """A port named like a settings field (e.g. a 'width' outlet colliding with
    props.width) must not swallow a prefer_setting write — regression: the
    resize commit didn't stick on nodes with width/height outlets."""
    from haywire.barn.builtin.types import FLOAT

    graph, editor = graph_and_editor
    wrapper = _add_node(editor)
    node = wrapper.node
    node.add(FLOAT.as_outlet("width", label="Width"))
    node.ports["width"].set_value(7.0)
    props_before = node.props.width

    # Default resolution: port wins.
    assert editor.set_property(wrapper.node_id, "width", 999.0) is True
    assert node.ports["width"].get_value() == 999.0
    assert node.props.width == props_before

    # prefer_setting: the settings bag wins.
    assert editor.set_property(wrapper.node_id, "width", 333.0, prefer_setting=True) is True
    assert node.props.width == 333.0
    assert node.ports["width"].get_value() == 999.0  # port untouched

    # Undo restores the bag write, not the port.
    assert editor.undo() is True
    assert node.props.width == props_before
    assert node.ports["width"].get_value() == 999.0


def test_unknown_node_returns_false(graph_and_editor):
    _, editor = graph_and_editor
    assert editor.set_property("no_such_node", "x", 1) is False


def test_unknown_name_returns_false(graph_and_editor):
    _, editor = graph_and_editor
    wrapper = _add_node(editor)
    assert editor.set_property(wrapper.node_id, "no_such_property", 1) is False
    # nothing half-applied: no undoable action was recorded for the failed set
    assert editor.can_undo() is True  # the create_wrapper is still undoable


def test_action_serializes(graph_and_editor):
    from haywire.core.undo.actions.graph_actions import SetPropertyAction

    graph, editor = graph_and_editor
    wrapper = _add_node(editor)
    port_id = next(pid for pid, p in wrapper.node.ports.items() if p.is_inlet())
    action = SetPropertyAction(graph, wrapper.node_id, port_id, 1.0)
    action.execute()
    d = action.to_dict()
    assert d["action_type"] == "SetPropertyAction"
    assert d["executed"] is True


POOLED_NODE_KEY = "haybale-testing:node:EdgeLinkTestNode"  # has pooled_float_inlet


def _history(editor) -> dict:
    stats = editor.history_manager.get_history_stats()
    return {k: stats[k] for k in ("total_items", "action_count", "pending_actions")}


def test_a_pooled_inlet_refuses_a_property_write(graph_and_editor):
    """A pooled inlet's value comes only from its edges: the write is refused, not swallowed."""
    graph, editor = graph_and_editor
    wrapper = _add_node(editor, POOLED_NODE_KEY)
    port = wrapper.node.ports["pooled_float_inlet"]
    pool_before = dict(port.data.get_value())
    history_before = _history(editor)

    assert editor.set_property(wrapper.node_id, "pooled_float_inlet", 3.0) is False

    assert dict(port.data.get_value()) == pool_before
    assert _history(editor) == history_before


def test_an_add_slot_refuses_a_property_write(graph_and_editor):
    graph, editor = graph_and_editor
    from haybale_testing.nodes.testbed.add_port_test import AddPortTestNode

    wrapper = _add_node(editor, AddPortTestNode.class_identity.registry_key)
    assert isinstance(wrapper.node, AddPortTestNode)
    assert "add_in_0" in wrapper.node.ports
    history_before = _history(editor)

    assert editor.set_property(wrapper.node_id, "add_in_0", 3.0) is False

    assert _history(editor) == history_before


def test_the_refusal_names_the_mechanism(graph_and_editor):
    from haywire.core.undo.actions.graph_actions import SetPropertyAction

    graph, editor = graph_and_editor
    wrapper = _add_node(editor, POOLED_NODE_KEY)
    action = SetPropertyAction(graph, wrapper.node_id, "pooled_float_inlet", 3.0)

    with pytest.raises(ValueError, match="holds no own value.*only from its edges"):
        action._resolve()


def test_a_linked_inlet_that_accepts_an_own_value_still_takes_a_property_write(graph_and_editor):
    """The refusal is for a field with no own value; an edge into a FLOAT inlet leaves it writable."""
    graph, editor = graph_and_editor
    source = _add_node(editor)
    sink = _add_node(editor)
    assert editor.create_edge(source.node_id, "result", sink.node_id, "value_a") is True
    inlet = sink.node.ports["value_a"]
    assert inlet.incoming.linked
    assert inlet.data.accepts_own_value()

    assert editor.set_property(sink.node_id, "value_a", 42.0) is True

    assert inlet.data.get_own_value() == 42.0


def test_undo_on_a_linked_inlet_restores_the_own_value_not_the_edges(graph_and_editor):
    graph, editor = graph_and_editor
    source = _add_node(editor)
    sink = _add_node(editor)
    assert editor.create_edge(source.node_id, "result", sink.node_id, "value_a") is True
    inlet = sink.node.ports["value_a"]
    inlet.data.set_value(7.0, source_id="edge-1")  # the edge's value stands in front
    inlet.data.set_value(0.0)
    assert inlet.data.get_own_value() == 0.0

    assert editor.set_property(sink.node_id, "value_a", 42.0) is True
    assert inlet.data.get_own_value() == 42.0

    assert editor.undo() is True
    assert inlet.data.get_own_value() == 0.0
    assert inlet.get_value() == 7.0  # the edge's value is untouched


@pytest.fixture
def held_editor(library_system):
    """An editor on a graph whose debounce never fires on its own, so a test drains it explicitly."""
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.editor import Editor
    from haywire.core.graph.scheduler import ThreadingTimerScheduler
    from haywire.core.undo.config import UndoConfig

    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    config = UndoConfig(enable_auto_grouping=False, enable_action_merging=False)
    yield graph, Editor(graph, library_system.get_node_factory(), undo_config=config)
    graph._validation.clear()
    graph.cleanup()


def test_setting_the_current_value_marks_nothing(held_editor):
    from haywire.core.graph.types import ChangeReason

    graph, editor = held_editor
    port_node = _add_node(editor)
    settings_node = _add_node(editor, SETTINGS_NODE_KEY)
    settings_node.node.example.persistent_value = 5.0
    current = port_node.node.ports["value_a"].data.get_own_value()
    graph._validation.force_immediate_validation()

    assert editor.set_property(port_node.node_id, "value_a", current) is True
    assert editor.set_property(settings_node.node_id, "persistent_value", 5.0) is True
    assert graph._validation.force_immediate_validation() is None

    assert editor.set_property(port_node.node_id, "value_a", current + 1) is True
    result = graph._validation.force_immediate_validation()
    assert result is not None
    assert result.nodes == {port_node.node_id: ChangeReason.NODE_VALUE_CHANGED}


def test_record_false_leaves_no_undo_step(held_editor):
    from tests.conftest import make_node

    graph, editor = held_editor
    wrapper = make_node(graph, PORT_NODE_KEY)

    assert editor.set_property(wrapper.node_id, "value_a", 42.0, record=False) is True

    assert wrapper.node.ports["value_a"].get_value() == 42.0
    assert editor.can_undo() is False
