"""Split Path: a volume path into volume, base, subfolder, stem, extension and on-disk locations."""

import importlib
from typing import Any
from unittest.mock import MagicMock

import pytest

from haywire.core.volumes import VolumePath, get_volume_store
from tests.conftest import make_edge, make_node
from tests.core.test_execution.test_for_each_file import _Runner

pytestmark = pytest.mark.integration

SCANS = "user:volume:scans"
PATH_OUTLETS = ("volume", "base", "parent")
TEXT_OUTLETS = (
    "base_folder",
    "subfolder",
    "folder",
    "stem",
    "extension",
    "name",
    "base_on_disk",
    "parent_on_disk",
    "path_on_disk",
)


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _linked_split(graph: Any) -> Any:
    """A Split Path whose every outlet feeds an Output Path, so every outlet is worked out."""
    node = _add(graph, "haybale_core.nodes.split_path", "SplitPathNode")
    for outlet in PATH_OUTLETS + TEXT_OUTLETS:
        sink = _add(graph, "haybale_core.nodes.output_path", "OutputPathNode")
        make_edge(graph, node.node_id, outlet, sink.node_id, "folder" if outlet in PATH_OUTLETS else "stem")
    return node


def _split(graph: Any, path: VolumePath) -> dict[str, Any]:
    node = _linked_split(graph)
    node.worker(MagicMock(), path=path)
    return {pid: node.ports[pid].get_value() for pid in PATH_OUTLETS + TEXT_OUTLETS}


def test_splits_a_listed_path_at_its_base(graph_with_library_system):
    parts = _split(graph_with_library_system, VolumePath(SCANS, "in/a/b/x.png", base="in"))
    assert parts["volume"] == VolumePath(SCANS, "")
    assert parts["base"] == VolumePath(SCANS, "in")
    assert parts["parent"] == VolumePath(SCANS, "in/a/b")
    assert parts["base_folder"] == "in"
    assert parts["subfolder"] == "a/b"
    assert parts["folder"] == "in/a/b"
    assert parts["stem"] == "x"
    assert parts["extension"] == ".png"
    assert parts["name"] == "x.png"


def test_a_file_right_in_its_base_has_no_subfolder(graph_with_library_system):
    parts = _split(graph_with_library_system, VolumePath(SCANS, "in/x.png", base="in"))
    assert parts["base_folder"] == "in"
    assert parts["subfolder"] == ""
    assert parts["base"] == parts["parent"] == VolumePath(SCANS, "in")


def test_a_path_without_base_has_its_whole_folder_as_subfolder(graph_with_library_system):
    parts = _split(graph_with_library_system, VolumePath(SCANS, "a/b/x.png"))
    assert parts["base_folder"] == ""
    assert parts["base"] == VolumePath(SCANS, "")
    assert parts["subfolder"] == parts["folder"] == "a/b"


def test_root_file(graph_with_library_system):
    parts = _split(graph_with_library_system, VolumePath(SCANS, "x"))
    assert parts["folder"] == parts["subfolder"] == parts["extension"] == ""
    assert parts["parent"] == VolumePath(SCANS, "")


def test_on_disk_parts_resolve_and_stay_empty_without_the_volume(graph_with_library_system, tmp_path):
    get_volume_store().add(SCANS, label="Scans", description="", location=tmp_path)
    parts = _split(graph_with_library_system, VolumePath(SCANS, "in/a/x.png", base="in"))
    assert parts["base_on_disk"] == str(tmp_path / "in")
    assert parts["parent_on_disk"] == str(tmp_path / "in" / "a")
    assert parts["path_on_disk"] == str(tmp_path / "in" / "a" / "x.png")

    parts = _split(graph_with_library_system, VolumePath("user:volume:nowhere", "x.png"))
    assert parts["path_on_disk"] == ""
    assert parts["stem"] == "x"


def test_a_new_node_shows_folder_stem_and_extension_only(graph_with_library_system):
    node = _add(graph_with_library_system, "haybale_core.nodes.split_path", "SplitPathNode")
    shown = {p.id for p in node.get_visible_ports() if p.is_outlet()}
    assert shown == {"folder", "stem", "extension"}


def test_only_connected_outlets_are_worked_out(graph_with_library_system):
    graph = graph_with_library_system
    node = _add(graph, "haybale_core.nodes.split_path", "SplitPathNode")
    sink = _add(graph, "haybale_core.nodes.output_path", "OutputPathNode")
    make_edge(graph, node.node_id, "stem", sink.node_id, "stem")

    node.worker(MagicMock(), path=VolumePath(SCANS, "a/x.png"))

    assert node.ports["stem"].get_value() == "x"
    assert node.ports["folder"].get_value() == ""
    assert node.ports["name"].get_value() == ""


def test_an_outlet_connected_later_delivers_on_the_next_run(graph_with_library_system, monkeypatch):
    """The node ran with the outlet unconnected; a new edge alone makes the next run deliver it."""
    graph = graph_with_library_system
    begin = _add(graph, "haybale_core.nodes.events.begin_play", "BeginPlayNode")
    split = _add(graph, "haybale_core.nodes.split_path", "SplitPathNode")
    first = _add(graph, "haybale_core.nodes.logger", "LoggerNode")
    second = _add(graph, "haybale_core.nodes.logger", "LoggerNode")
    split.ports["path"].set_value(VolumePath(SCANS, "a/x.png"))
    make_edge(graph, begin.node_id, "exec", first.node_id, "exec")
    make_edge(graph, first.node_id, "done", second.node_id, "exec")
    make_edge(graph, split.node_id, "stem", first.node_id, "message")
    heard: list[str] = []

    def record(context: Any, prepend: str) -> None:
        heard.append(second.value("message"))

    second.worker = record

    _Runner(graph, monkeypatch).fire(begin)
    make_edge(graph, split.node_id, "name", second.node_id, "message")
    _Runner(graph, monkeypatch).fire(begin)

    assert heard[-1] == "x.png"


@pytest.mark.parametrize(
    ("relative", "base"), [("in/a/b/x.png", "in"), ("in/x.png", "in"), ("a/x", ""), ("x.png", "")]
)
def test_round_trips_through_output_path(graph_with_library_system, relative, base):
    graph = graph_with_library_system
    original = VolumePath(SCANS, relative, base=base)
    parts = _split(graph, original)
    out = _add(graph, "haybale_core.nodes.output_path", "OutputPathNode")
    out.worker(
        MagicMock(),
        folder=parts["base"],
        subdir=parts["subfolder"],
        stem=parts["stem"],
        extension=parts["extension"],
    )
    assert out.ports["path"].get_value() == original
