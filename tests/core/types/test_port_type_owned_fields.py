"""A saved port leaves out what its type says, and takes it back from the type on load."""

from __future__ import annotations

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.types.port import DataPort

from tests.conftest import make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"

#: Fields of ``FLOAT``'s identity that no port of ``TestAddFloatNode`` overrides.
_TYPE_OWNED = ("registry_id", "registry_key", "class_name", "module", "color", "widget_key")


@pytest.fixture
def held_graph(library_system):
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    yield graph
    graph._validation.clear()
    graph.cleanup()


def test_a_saved_port_leaves_out_what_its_type_says(held_graph: BaseGraph):
    port = make_node(held_graph, _ADD).node.ports["value_a"]

    saved = port.to_dict()

    for name in _TYPE_OWNED:
        assert getattr(port, name) == getattr(FLOAT.class_identity, name)
        assert name not in saved["kwargs"], name
    assert saved["kwargs"]["id"] == "value_a"
    assert saved["recipe"] == {"registry_key": FLOAT.class_identity.registry_key}


def test_a_saved_port_keeps_what_its_author_overrode(held_graph: BaseGraph):
    node = make_node(held_graph, _ADD).node
    port = node.add(FLOAT.as_inlet("tinted", color="#123456", description="Mine"))

    saved = port.to_dict()

    assert saved["kwargs"]["color"] == "#123456"
    assert saved["kwargs"]["description"] == "Mine"


def test_an_override_equal_to_the_field_default_is_kept(held_graph: BaseGraph):
    node = make_node(held_graph, _ADD).node
    field_default = DataPort.__dataclass_fields__["color"].default
    assert FLOAT.class_identity.color != field_default
    port = node.add(FLOAT.as_inlet("grey", color=field_default))

    assert port.to_dict()["kwargs"]["color"] == field_default


def test_a_loaded_port_takes_the_rest_from_its_type(held_graph: BaseGraph):
    node = make_node(held_graph, _ADD).node
    port = node.ports["value_a"]
    saved = port.to_dict()

    loaded = DataPort.from_spec(saved, node._type_registry, node.wrapper, node)

    for name in (*_TYPE_OWNED, "label", "description", "store_strategy", "show_widget", "default"):
        assert getattr(loaded, name) == getattr(port, name), name
    assert loaded.get_value() == port.get_value()


def test_a_change_to_the_type_reaches_a_saved_port(held_graph: BaseGraph, monkeypatch):
    node = make_node(held_graph, _ADD).node
    saved = node.ports["value_a"].to_dict()

    monkeypatch.setattr(FLOAT.class_identity, "color", "#abcdef")
    loaded = DataPort.from_spec(saved, node._type_registry, node.wrapper, node)

    assert loaded.color == "#abcdef"
