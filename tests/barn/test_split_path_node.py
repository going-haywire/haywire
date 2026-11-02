"""Split Path: a volume path into volume, base, subfolder, stem, extension and on-disk locations."""

import importlib
from typing import Any
from unittest.mock import MagicMock

import pytest

from haywire.core.node.promotion import demote_setting, eligible_promotion_directions, promote_setting
from haywire.core.settings import UiState
from haywire.core.types.enums import PortType
from haywire.core.volumes import VolumePath, get_volume_store
from tests.conftest import make_node

from haybale_core.nodes.split_path import NOT_EVALUATED, READY

pytestmark = pytest.mark.integration

SCANS = "user:volume:scans"


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


PATH_PARTS = ("volume", "base", "parent")
TEXT_PARTS = (
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


def _split_node(graph: Any, *, promote_all: bool = True) -> Any:
    node = _add(graph, "haybale_core.nodes.split_path", "SplitPathNode")
    if promote_all:
        for part in PATH_PARTS + TEXT_PARTS:
            promote_setting(node, "parts", part, PortType.OUTLET)
    return node


def _split(graph: Any, path: VolumePath) -> Any:
    node = _split_node(graph)
    node.worker(MagicMock(), path=path)
    return node


def test_splits_a_listed_path_at_its_base(graph_with_library_system):
    parts = _split(graph_with_library_system, VolumePath(SCANS, "in/a/b/x.png", base="in")).parts
    assert parts.volume == VolumePath(SCANS, "")
    assert parts.base == VolumePath(SCANS, "in")
    assert parts.parent == VolumePath(SCANS, "in/a/b")
    assert parts.base_folder == "in"
    assert parts.subfolder == "a/b"
    assert parts.folder == "in/a/b"
    assert parts.stem == "x"
    assert parts.extension == ".png"
    assert parts.name == "x.png"


def test_a_file_right_in_its_base_has_no_subfolder(graph_with_library_system):
    parts = _split(graph_with_library_system, VolumePath(SCANS, "in/x.png", base="in")).parts
    assert parts.base_folder == "in"
    assert parts.subfolder == ""
    assert parts.base == parts.parent == VolumePath(SCANS, "in")


def test_a_path_without_base_has_its_whole_folder_as_subfolder(graph_with_library_system):
    parts = _split(graph_with_library_system, VolumePath(SCANS, "a/b/x.png")).parts
    assert parts.base_folder == ""
    assert parts.base == VolumePath(SCANS, "")
    assert parts.subfolder == parts.folder == "a/b"


def test_root_file(graph_with_library_system):
    parts = _split(graph_with_library_system, VolumePath(SCANS, "x")).parts
    assert parts.folder == parts.subfolder == parts.extension == ""
    assert parts.parent == VolumePath(SCANS, "")


def test_on_disk_parts_resolve_and_stay_empty_without_the_volume(graph_with_library_system, tmp_path):
    get_volume_store().add(SCANS, label="Scans", description="", location=tmp_path)
    parts = _split(graph_with_library_system, VolumePath(SCANS, "in/a/x.png", base="in")).parts
    root = tmp_path.resolve()
    assert parts.base_on_disk == str(root / "in")
    assert parts.parent_on_disk == str(root / "in" / "a")
    assert parts.path_on_disk == str(root / "in" / "a" / "x.png")

    parts = _split(graph_with_library_system, VolumePath("user:volume:nowhere", "x.png")).parts
    assert parts.path_on_disk == ""
    assert parts.stem == "x"


def test_folder_stem_and_extension_are_outlets_on_a_new_node(graph_with_library_system):
    node = _split_node(graph_with_library_system, promote_all=False)
    node.worker(MagicMock(), path=VolumePath(SCANS, "a/x.png"))
    outlets = {p.id for p in node.ports.values() if p.port_type is PortType.OUTLET}
    assert outlets == {"parts.folder", "parts.stem", "parts.extension"}
    assert node.ports["parts.folder"].get_value() == "a"


def test_parts_not_promoted_are_not_worked_out(graph_with_library_system):
    node = _split_node(graph_with_library_system, promote_all=False)
    node.worker(MagicMock(), path=VolumePath(SCANS, "in/a/x.png", base="in"))
    assert node.parts.stem == "x"
    assert node.parts.subfolder == node.parts.name == node.parts.path_on_disk == NOT_EVALUATED


def test_promoting_a_part_runs_the_node_again(graph_with_library_system):
    node = _split_node(graph_with_library_system, promote_all=False)
    node.worker(MagicMock(), path=VolumePath(SCANS, "in/a/x.png", base="in"))
    node._has_run = True

    promote_setting(node, "parts", "subfolder", PortType.CONFIG)

    assert node._has_run is False
    assert node.parts.subfolder == READY


def test_a_new_node_shows_its_outlets_ready():
    from haybale_core.nodes.split_path import SplitPathParts

    parts = SplitPathParts()
    assert parts.folder == parts.stem == parts.extension == READY
    assert parts.subfolder == NOT_EVALUATED


def test_demoting_a_part_shows_the_placeholder_again(graph_with_library_system):
    node = _split_node(graph_with_library_system, promote_all=False)
    node.worker(MagicMock(), path=VolumePath(SCANS, "a/x.png"))
    assert node.parts.stem == "x"

    demote_setting(node, "parts.stem")

    assert node.parts.stem == NOT_EVALUATED


def test_path_parts_show_no_widget(graph_with_library_system):
    node = _split_node(graph_with_library_system, promote_all=False)
    for part in PATH_PARTS:
        assert node.parts._effective_ui_state(part) is UiState.HIDE_WIDGET


def test_path_parts_promote_to_outlets_only(graph_with_library_system):
    from haybale_core.nodes.split_path import SplitPathParts

    descriptors = SplitPathParts._settings_descriptors()
    for name in ("volume", "base", "parent"):
        assert eligible_promotion_directions(descriptors[name]) == (PortType.OUTLET,)
    assert eligible_promotion_directions(descriptors["subfolder"]) == (PortType.OUTLET, PortType.CONFIG)


@pytest.mark.parametrize(
    ("relative", "base"), [("in/a/b/x.png", "in"), ("in/x.png", "in"), ("a/x", ""), ("x.png", "")]
)
def test_round_trips_through_output_path(graph_with_library_system, relative, base):
    graph = graph_with_library_system
    original = VolumePath(SCANS, relative, base=base)
    parts = _split(graph, original).parts
    out = _add(graph, "haybale_core.nodes.output_path", "OutputPathNode")
    out.worker(
        MagicMock(),
        folder=parts.base,
        subdir=parts.subfolder,
        stem=parts.stem,
        extension=parts.extension,
    )
    assert out.ports["path"].get_value() == original
