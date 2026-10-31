"""A copied callback listener publishes the name it listens on: its own node id, not the original's."""

import importlib

import pytest

from tests.conftest import make_node

pytestmark = pytest.mark.integration

LISTENERS = [
    ("haybale_core.nodes.events.tick_event", "TickEventNode"),
    ("haybale_example.nodes.emits.custom_callback", "CustomCallbackNode"),
    ("haybale_testing.nodes.testbed.custom_callback_node", "TestCustomCallbackNode"),
]


@pytest.mark.parametrize(("module", "name"), LISTENERS)
def test_a_pasted_listener_publishes_its_own_id(graph_with_library_system, library_system, module, name):
    from haywire.core.graph.clipboard import build_clipboard_payload
    from haywire.core.graph.editor import Editor

    graph = graph_with_library_system
    cls = getattr(importlib.import_module(module), name)
    original = make_node(graph, cls.class_identity.registry_key).node
    assert isinstance(original, cls), "an unknown key yields an ErrorNode"

    payload = build_clipboard_payload(graph, [original.node_id], [], "session")
    pasted = Editor(graph, library_system.get_node_factory()).paste_clipboard(payload, 500.0, 500.0)
    assert pasted is not None
    copy = graph.node_wrappers[pasted[0][0]].node

    assert copy.node_id != original.node_id
    assert copy.ports["listen_callback"].get_value() == copy.node_id
    assert copy.event_subscription.event_name == copy.node_id
    assert original.ports["listen_callback"].get_value() == original.node_id
