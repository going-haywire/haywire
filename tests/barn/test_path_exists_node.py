"""Path Exists?: branch on whether a volume path is there; an unresolvable path is an error."""

import importlib
from typing import Any

import pytest

from haywire.core.volumes import VolumeEscapeError, VolumePath, VolumeUndefinedError, get_volume_store
from tests.conftest import make_node

pytestmark = pytest.mark.integration

SCANS = "user:volume:scans"


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _node(graph: Any) -> Any:
    return _add(graph, "haybale_core.nodes.path_exists", "PathExistsNode")


@pytest.fixture
def scans(tmp_path):
    (tmp_path / "a.png").write_bytes(b"x")
    (tmp_path / "sub").mkdir()
    get_volume_store().add(SCANS, label="Scans", description="", location=tmp_path)
    return tmp_path


def _branch(node: Any, path: VolumePath) -> str:
    return node.worker(None, path=path)


def test_file_exists(graph_with_library_system, scans):
    assert _branch(_node(graph_with_library_system), VolumePath(SCANS, "a.png")) == "exists"


def test_folder_exists(graph_with_library_system, scans):
    assert _branch(_node(graph_with_library_system), VolumePath(SCANS, "sub")) == "exists"


def test_missing(graph_with_library_system, scans):
    assert _branch(_node(graph_with_library_system), VolumePath(SCANS, "b.png")) == "missing"


def test_undefined_volume_raises(graph_with_library_system, scans):
    with pytest.raises(VolumeUndefinedError):
        _branch(_node(graph_with_library_system), VolumePath("user:volume:nowhere", "a"))


def test_escape_raises(graph_with_library_system, scans):
    with pytest.raises(VolumeEscapeError):
        _branch(_node(graph_with_library_system), VolumePath(SCANS, "../x"))


def test_accepts_file_path_wires(graph_with_library_system):
    graph = graph_with_library_system
    source = _add(graph, "haybale_core.nodes.output_path", "OutputPathNode")
    node = _node(graph)

    edge = graph.create_edge_wrapper(source.node_id, "path", node.node_id, "path")

    assert edge is not None
    assert node.ports["path"].data.has_linked_value()
