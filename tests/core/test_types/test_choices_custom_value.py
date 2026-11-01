"""A CHOICES value that is not one of its options survives save, load, copy and undo.

A select with ``new_value_mode`` lets the user type such a value. The value is a
plain string; the options are presentation and must not pick it up.
"""

import importlib
from typing import Any

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.clipboard import build_clipboard_payload
from haywire.core.graph.setting_owner import setting_owner
from haywire.core.node.promotion import promote_setting
from haywire.core.types.enums import PortType
from haywire.core.undo.actions.graph_actions import PasteClipboardAction, SetSettingAction
from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _restored(graph: BaseGraph, wrapper: Any) -> Any:
    data = wrapper.serialize(include_data=True)["node_data"]
    restored = make_node(graph, wrapper.node.class_identity.registry_key, position=(500, 0))
    restored.node._initialize_from_dict(data)
    return restored


def _pasted(graph: BaseGraph, wrapper: Any) -> Any:
    payload = build_clipboard_payload(graph, [wrapper.node_id], [], session_id="s")
    action = PasteClipboardAction(graph=graph, payload=payload, paste_x=900.0, paste_y=900.0)
    action.execute()
    (node_id,) = action.new_node_ids
    return graph.get_node_wrapper(node_id)


@pytest.mark.parametrize("promoted", [False, True])
def test_a_custom_setting_value_round_trips(graph_with_library_system: BaseGraph, library_system, promoted):
    graph = graph_with_library_system
    cls = importlib.import_module("haybale_testing.nodes.testbed.settings_node").SettingsNode
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    if promoted:
        promote_setting(wrapper.node, "example", "example_choices", direction=PortType.INLET)
    owner = setting_owner(graph, wrapper.node.example)
    assert owner is not None

    action = SetSettingAction(graph, owner, "example_choices", "custom-mode")
    action.execute()
    assert wrapper.node.example.example_choices == "custom-mode"

    assert _restored(graph, wrapper).node.example.example_choices == "custom-mode"
    assert _pasted(graph, wrapper).node.example.example_choices == "custom-mode"

    action.undo()
    assert wrapper.node.example.example_choices == "fast"


def test_a_custom_value_on_a_plain_port_round_trips_and_its_options_stay_declared(
    graph_with_library_system: BaseGraph, library_system
):
    graph = graph_with_library_system
    cls = importlib.import_module("haybale_image.nodes.save_image").SaveImageNode
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    declared = list(wrapper.node.ports["depth"].widget_config["properties"]["options"])
    wrapper.node.ports["depth"].set_value("64")

    for copy in (_restored(graph, wrapper), _pasted(graph, wrapper)):
        port = copy.node.ports["depth"]
        assert port.get_value() == "64"
        assert port.widget_config["properties"]["options"] == declared
