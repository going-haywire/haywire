"""A node's declaration, and a saved port holding only what differs from it."""

from __future__ import annotations

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.node.node_wrapper import NodeWrapper

from tests.conftest import make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"


@pytest.fixture
def held_graph(library_system):
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    yield graph
    graph._validation.clear()
    graph.cleanup()


def _rebuilt(graph: BaseGraph, wrapper: NodeWrapper) -> NodeWrapper:
    """Return a second node built from *wrapper*'s saved data, as a load builds it."""
    saved = wrapper.serialize()
    copy = NodeWrapper(registry_key=saved["registry_key"], node_id="copy", graph=graph)
    copy.build(saved["node_data"])
    return copy


def test_the_declaration_holds_the_ports_init_adds(held_graph: BaseGraph):
    node = make_node(held_graph, _ADD).node

    assert set(node.declaration) == set(node.ports)
    assert node.declaration["value_a"]["kwargs"]["label"] == node.ports["value_a"].label


def test_a_port_added_after_init_is_not_declared(held_graph: BaseGraph):
    node = make_node(held_graph, _ADD).node
    node.add(FLOAT.as_inlet("grown"))

    assert "grown" not in node.declaration


def test_an_untouched_declared_port_saves_only_its_floor(held_graph: BaseGraph):
    wrapper = make_node(held_graph, _ADD)

    saved = wrapper.serialize()["node_data"]["ports"]["value_a"]

    assert saved["kwargs"] == {"id": "value_a", "port_type": "inlet"}


def test_a_changed_field_of_a_declared_port_is_saved(held_graph: BaseGraph):
    wrapper = make_node(held_graph, _ADD)
    wrapper.node.ports["value_a"].hidden = True

    saved = wrapper.serialize()["node_data"]["ports"]["value_a"]

    assert saved["kwargs"] == {"id": "value_a", "port_type": "inlet", "hidden": True}


def test_a_field_changed_back_to_its_default_is_saved(held_graph: BaseGraph):
    wrapper = make_node(held_graph, _ADD)
    port = wrapper.node.ports["value_a"]
    declared = port.label
    port.label = ""

    saved = wrapper.serialize()["node_data"]["ports"]["value_a"]
    assert saved["kwargs"]["label"] == ""

    assert _rebuilt(held_graph, wrapper).node.ports["value_a"].label == ""
    assert declared != ""


def test_a_loaded_node_takes_the_rest_from_its_declaration(held_graph: BaseGraph):
    wrapper = make_node(held_graph, _ADD)
    wrapper.node.ports["value_a"].hidden = True
    wrapper.node.ports["value_a"].set_value(4.5)

    loaded = _rebuilt(held_graph, wrapper).node

    for port_id, port in wrapper.node.ports.items():
        assert loaded.ports[port_id].to_dict() == port.to_dict(), port_id
    assert loaded.ports["value_a"].hidden is True
    assert loaded.ports["value_a"].get_value() == 4.5
    assert loaded.declaration == wrapper.node.declaration


def test_a_port_the_file_leaves_out_stays_out(held_graph: BaseGraph):
    wrapper = make_node(held_graph, _ADD)
    with wrapper.node.rejig(include=["value_b"]):
        pass

    loaded = _rebuilt(held_graph, wrapper).node

    assert "value_b" not in loaded.ports
    assert "value_b" in loaded.declaration


def test_a_grown_port_is_saved_whole_and_comes_back(held_graph: BaseGraph):
    wrapper = make_node(held_graph, _ADD)
    wrapper.node.add(FLOAT.as_inlet("grown", label="Grown"))

    saved = wrapper.serialize()["node_data"]["ports"]["grown"]
    assert saved["kwargs"]["label"] == "Grown"

    assert _rebuilt(held_graph, wrapper).node.ports["grown"].label == "Grown"


def test_a_retyped_declared_port_is_saved_whole(held_graph: BaseGraph):
    from haywire.barn.builtin.types import INT

    wrapper = make_node(held_graph, _ADD)
    label = wrapper.node.ports["value_a"].label
    with wrapper.node.rejig(include=["value_a"]):
        wrapper.node.add(INT.as_inlet("value_a", label=label))

    saved = wrapper.serialize()["node_data"]["ports"]["value_a"]
    assert saved["kwargs"]["label"] == label

    loaded = _rebuilt(held_graph, wrapper).node.ports["value_a"]
    assert loaded.type_cls is INT
    assert loaded.label == label


def test_a_code_change_to_a_declared_label_reaches_a_saved_node(held_graph: BaseGraph, monkeypatch):
    wrapper = make_node(held_graph, _ADD)
    saved = wrapper.serialize()
    node_cls = type(wrapper.node)
    original_init = node_cls.init

    def init(self) -> None:
        original_init(self)
        self.ports["value_a"].label = "Renamed"

    monkeypatch.setattr(node_cls, "init", init)
    loaded = NodeWrapper(registry_key=saved["registry_key"], node_id="copy", graph=held_graph)
    loaded.build(saved["node_data"])

    assert loaded.node.ports["value_a"].label == "Renamed"


# ---------------------------------------------------------------------------
# Ports saved by a file older than format v5
# ---------------------------------------------------------------------------


def _as_v4(wrapper: NodeWrapper) -> dict:
    """Return *wrapper*'s node data with every port saved whole, as format v4 saved it."""
    data = wrapper.serialize()["node_data"]
    data["ports"] = {port_id: port.to_dict() for port_id, port in wrapper.node.ports.items()}
    data["legacy_ports"] = True
    return data


def _built(graph: BaseGraph, wrapper: NodeWrapper, data: dict) -> NodeWrapper:
    copy = NodeWrapper(registry_key=wrapper.registry_key, node_id="copy", graph=graph)
    copy.build(data)
    return copy


def test_a_legacy_declared_port_takes_its_fields_from_the_code(held_graph: BaseGraph):
    wrapper = make_node(held_graph, _ADD)
    declared = wrapper.node.ports["value_a"].description
    data = _as_v4(wrapper)
    data["ports"]["value_a"]["kwargs"]["description"] = "What the code said long ago"
    data["ports"]["value_a"]["kwargs"]["store_strategy"] = 14

    loaded = _built(held_graph, wrapper, data).node.ports["value_a"]

    assert loaded.description == declared
    assert loaded.store_strategy == wrapper.node.ports["value_a"].store_strategy


def test_a_legacy_declared_port_keeps_order_hidden_and_value(held_graph: BaseGraph):
    wrapper = make_node(held_graph, _ADD)
    port = wrapper.node.ports["value_b"]
    port.hidden = True
    port.set_value(7.25)
    data = _as_v4(wrapper)
    data["ports"]["value_b"]["kwargs"].pop("order", None)

    loaded = _built(held_graph, wrapper, data).node.ports["value_b"]

    assert loaded.hidden is True
    assert loaded.get_value() == 7.25
    assert loaded.order == 0


def test_a_legacy_grown_port_keeps_what_the_file_says(held_graph: BaseGraph):
    wrapper = make_node(held_graph, _ADD)
    wrapper.node.add(FLOAT.as_inlet("grown", label="Grown", description="Kept"))

    loaded = _built(held_graph, wrapper, _as_v4(wrapper)).node.ports["grown"]

    assert (loaded.label, loaded.description) == ("Grown", "Kept")


def test_a_saved_node_drops_the_legacy_mark(held_graph: BaseGraph):
    wrapper = make_node(held_graph, _ADD)

    saved = _built(held_graph, wrapper, _as_v4(wrapper)).serialize()["node_data"]

    assert "legacy_ports" not in saved
    assert saved["ports"]["value_a"]["kwargs"] == {"id": "value_a", "port_type": "inlet"}
