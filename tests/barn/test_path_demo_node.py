"""PathDemoNode: one port per path type, each resolved to an absolute path on its outlet."""

import importlib
from typing import Any
from unittest.mock import MagicMock

import pytest

from haywire.core.di import context
from haywire.core.volumes import PROJECT_KEY, VolumePath, get_volume_store
from tests.conftest import make_node

pytestmark = pytest.mark.integration

SCANS = "user:volume:scans"


def _demo_node(graph: Any) -> Any:
    # Imported at call time: a barn module reload would leave a top-level import stale.
    cls = importlib.import_module("haybale_example.nodes.path_demo").PathDemoNode
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def test_each_path_type_gets_the_path_widget_in_its_mode(graph_with_library_system):
    node = _demo_node(graph_with_library_system)

    def widget(port_id: str) -> tuple[str, dict]:
        port = node.ports[port_id]
        return port.widget_key, port.widget_config.get("properties", {})

    assert widget("path")[0] == "haywire-core:widget:PathWidget"
    assert widget("file")[1]["mode"] == "file"
    assert widget("image")[1] == {"mode": "file", "extensions": [".png", ".jpg", ".jpeg"]}
    assert widget("folder")[1]["mode"] == "folder"
    assert widget("save_to")[1]["mode"] == "save"


def test_the_worker_resolves_every_port(graph_with_library_system, tmp_path):
    get_volume_store().add(SCANS, label="Scans", description="", location=tmp_path)
    node = _demo_node(graph_with_library_system)
    node.ports["path"].set_value(VolumePath(SCANS, "a"))
    node.ports["file"].set_value(VolumePath(SCANS, "b/c.txt"))
    node.ports["image"].set_value(VolumePath(SCANS, "d.png"))
    node.ports["folder"].set_value(VolumePath(SCANS, "e"))
    node.ports["save_to"].set_value(VolumePath(SCANS, "out/f.png"))

    node.worker(MagicMock(), **{pid: node.ports[pid].get_value() for pid in node.PATH_PORTS})

    real = tmp_path.resolve()
    assert node.ports["path_resolved"].get_value() == str(real / "a")
    assert node.ports["file_resolved"].get_value() == str(real / "b" / "c.txt")
    assert node.ports["image_resolved"].get_value() == str(real / "d.png")
    assert node.ports["folder_resolved"].get_value() == str(real / "e")
    assert node.ports["save_to_resolved"].get_value() == str(real / "out" / "f.png")
    assert node.ports["problems"].get_value() == ""


@pytest.fixture
def workspace_at_tmp(tmp_path):
    previous = context._workspace_root
    context.set_workspace_root(tmp_path)
    yield tmp_path
    context._workspace_root = previous


def test_an_unresolvable_port_is_empty_and_reported(graph_with_library_system, workspace_at_tmp):
    node = _demo_node(graph_with_library_system)
    values = {pid: VolumePath(PROJECT_KEY, "") for pid in node.PATH_PORTS}
    values["file"] = VolumePath(SCANS, "x.txt")
    values["folder"] = VolumePath(PROJECT_KEY, "../outside")

    node.worker(MagicMock(), **values)

    assert node.ports["file_resolved"].get_value() == ""
    assert node.ports["folder_resolved"].get_value() == ""
    problems = node.ports["problems"].get_value().splitlines()
    assert problems[0] == "file: volume 'user:volume:scans' is not defined on this machine"
    assert problems[1].startswith("folder: ")
    assert "escapes its volume" in problems[1]
    assert len(problems) == 2
    assert node.ports["path_resolved"].get_value() == str(workspace_at_tmp.resolve())
