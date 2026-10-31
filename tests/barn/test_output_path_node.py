"""Output Path: folder / subdir / stem + suffix + extension, in the folder's volume."""

import importlib
from typing import Any
from unittest.mock import MagicMock

import pytest

from haywire.core.volumes import VolumePath
from tests.conftest import make_node

pytestmark = pytest.mark.integration

SCANS = "user:volume:scans"


def _node(graph: Any) -> Any:
    cls = importlib.import_module("haybale_core.nodes.output_path").OutputPathNode
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _compose(node: Any, folder: VolumePath, subdir="", stem="img", suffix="", extension="png") -> VolumePath:
    node.worker(MagicMock(), folder=folder, subdir=subdir, stem=stem, suffix=suffix, extension=extension)
    return node.ports["path"].get_value()


def test_composes_folder_subdir_stem_suffix_extension(graph_with_library_system):
    node = _node(graph_with_library_system)
    assert _compose(node, VolumePath(SCANS, "out"), "a/b", "img", "_x4", "png") == VolumePath(
        SCANS, "out/a/b/img_x4.png"
    )


def test_top_level_from_for_each(graph_with_library_system):
    node = _node(graph_with_library_system)
    assert _compose(node, VolumePath(SCANS, "out"), "", "IMG_0002", "_x4", ".JPG") == VolumePath(
        SCANS, "out/IMG_0002_x4.JPG"
    )


@pytest.mark.parametrize(
    ("extension", "name"), [("png", "img.png"), (".png", "img.png"), ("..png", "img.png"), ("", "img")]
)
def test_extension_forms(graph_with_library_system, extension, name):
    node = _node(graph_with_library_system)
    assert _compose(node, VolumePath(SCANS, "out"), extension=extension) == VolumePath(SCANS, f"out/{name}")


def test_empty_segments_collapse(graph_with_library_system):
    node = _node(graph_with_library_system)
    assert _compose(node, VolumePath(SCANS, ""), "a//b/") == VolumePath(SCANS, "a/b/img.png")


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"stem": ""}, "stem is empty"),
        ({"stem": "a/b"}, "stem contains '/'"),
        ({"suffix": "x\\y"}, "suffix contains"),
        ({"extension": "p\0g"}, "extension contains"),
        ({"subdir": "/abs"}, "subdir is absolute"),
        ({"subdir": "C:/x"}, "subdir is absolute"),
        ({"subdir": "a/../b"}, "subdir contains '..'"),
    ],
)
def test_rejects(graph_with_library_system, kwargs, match):
    node = _node(graph_with_library_system)
    with pytest.raises(ValueError, match=match):
        _compose(node, VolumePath(SCANS, "out"), **kwargs)


def test_folder_outlet_is_parent(graph_with_library_system):
    node = _node(graph_with_library_system)
    _compose(node, VolumePath(SCANS, "out"), "a/b")
    assert node.ports["out_folder"].get_value() == VolumePath(SCANS, "out/a/b")
    _compose(node, VolumePath(SCANS, ""), "")
    assert node.ports["out_folder"].get_value() == VolumePath(SCANS, "")
