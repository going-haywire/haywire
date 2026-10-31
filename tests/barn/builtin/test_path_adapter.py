"""A path wired to a text inlet arrives as its display form, `volume name:relative`."""

import importlib
from typing import Any

import pytest

from haywire.core.volumes import VolumePath
from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def test_path_to_string_converts_to_the_display_form():
    from haywire.barn.builtin.adapters.path_adapters import PathToStringAdapter

    assert PathToStringAdapter().convert(VolumePath("user:volume:scans", "raw/a.png")) == "scans:raw/a.png"


def test_a_file_path_outlet_feeds_a_text_inlet(graph_with_library_system):
    graph = graph_with_library_system
    out = _add(graph, "haybale_core.nodes.output_path", "OutputPathNode")
    printer = _add(graph, "haybale_core.nodes.print", "PrintNode")
    out.ports["folder"].set_value(VolumePath("user:volume:scans", "out"))

    edge = graph.create_edge_wrapper(out.node_id, "path", printer.node_id, "message")
    assert edge is not None
    out.worker(None, folder=VolumePath("user:volume:scans", "out"), subdir="raw", stem="a", extension="png")

    assert printer.ports["message"].get_value() == "scans:out/raw/a.png"
