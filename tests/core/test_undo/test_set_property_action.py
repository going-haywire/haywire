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

    graph = BaseGraph("g", "g", validation_scheduler=SyncScheduler())
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
