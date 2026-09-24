"""studio_scaffold_component and studio_write_component_source over the authoring pipeline.

Both tools write into a throwaway library (``haybale_dst`` from the
authoring fixtures), never into a real barn library. A helper thread plays
the file watcher: it waits for the tool's write, then hands the registry the
file event, so the registration the tools report is the real one.
"""

import asyncio
import threading
import time
from pathlib import Path

import pytest

from haywire.core.farmhand import FarmhandContext, FarmhandError
from haywire.core.library.haybale_toml import read_haybale_toml
from haywire.core.library.install_type import InstallType
from haywire.core.library.registry import LibraryRegistry
from haywire.core.node.registry import NodeRegistry
from haywire.core.registry.base import FileChangeEvent, FileEventType

from tests.core.test_authoring import conftest as authoring

# The authoring fixtures, shared with tests/core/test_authoring.
packages = authoring.packages
dst_identity = authoring.dst_identity
dst_library = authoring.dst_library
FakeLibraries = authoring.FakeLibraries

pytestmark = [pytest.mark.unit, pytest.mark.core]


class _Libraries(FakeLibraries):
    """A LibraryRegistry holding the destination library as its one editable library."""

    def __init__(self, library, dists):
        super().__init__(library.identity, dists=dists)
        self._library = library

    def list_names(self):
        return ["dst", *super().list_names()]

    def get_library_install_type(self, library_id):
        return InstallType.EDITABLE if library_id == "dst" else InstallType.REGULAR

    def get_library(self, library_id):
        return self._library if library_id == "dst" else None


class _Context(FarmhandContext):
    def __init__(self, registries):
        super().__init__()
        self._registries = registries

    def registry(self, registry_cls):
        return self._registries[registry_cls]


@pytest.fixture
def setup(dst_library):
    node_registry = NodeRegistry()
    libraries = _Libraries(dst_library, dists={"src": "haybale-src"})
    ctx = _Context({LibraryRegistry: libraries, NodeRegistry: node_registry})
    return ctx, node_registry, dst_library.identity


def _watcher(registry, identity, path: Path, event_type, until) -> threading.Thread:
    """Dispatch ``event_type`` for ``path`` once ``until()`` holds, from another thread."""

    def _run():
        deadline = time.monotonic() + 5
        while not until() and time.monotonic() < deadline:
            time.sleep(0.01)
        registry.event_dispatcher(FileChangeEvent(str(path), event_type, identity, time.time()))

    thread = threading.Thread(target=_run)
    thread.start()
    return thread


def _run(tool_cls, ctx, **kwargs):
    return asyncio.run(tool_cls().run(ctx, **kwargs))


def test_scaffold_reports_the_key_that_actually_registered(setup):
    from haybale_studio.farmhands.authoring import StudioScaffoldComponentTool

    ctx, registry, identity = setup
    path = Path(identity.folder_path) / "nodes" / "blur_filter.py"
    thread = _watcher(registry, identity, path, FileEventType.CREATED, path.exists)

    result = _run(StudioScaffoldComponentTool, ctx, kind="node", name="blur_filter")
    thread.join()

    assert result["registration"] == "added"
    assert result["registry_key"] == "dst:node:BlurFilter"
    assert result["path"] == str(path)
    assert result["errors"] == []
    assert registry.get("dst:node:BlurFilter").class_identity.label == "BlurFilter"


def test_scaffold_keeps_a_pascal_case_name_and_takes_a_label(setup):
    from haybale_studio.farmhands.authoring import StudioScaffoldComponentTool

    ctx, registry, identity = setup
    path = Path(identity.folder_path) / "nodes" / "my_node.py"
    thread = _watcher(registry, identity, path, FileEventType.CREATED, path.exists)

    result = _run(StudioScaffoldComponentTool, ctx, kind="node", name="MyNode", label="My node")
    thread.join()

    assert result["registry_key"] == "dst:node:MyNode"
    assert registry.get("dst:node:MyNode").class_identity.label == "My node"


def test_scaffold_refuses_an_existing_file(setup):
    from haybale_studio.farmhands.authoring import StudioScaffoldComponentTool

    ctx, _registry, identity = setup
    (Path(identity.folder_path) / "nodes" / "taken.py").write_text("")

    with pytest.raises(FarmhandError) as exc_info:
        _run(StudioScaffoldComponentTool, ctx, kind="node", name="taken")
    assert exc_info.value.code == "file_exists"


_SOURCE = """\
from haywire.core.node import BaseNode, NodeType, node
from haybale_src.helpers import SCALE


@node(label="Scaled", node_type=NodeType.DATA)
class Scaled(BaseNode):
    def init(self):
        from haywire.barn.builtin.types import FLOAT

        self.add(FLOAT.as_outlet("r"))

    def worker(self, context):
        self.out("r", float(SCALE))
"""


def test_write_links_imported_libraries_and_reports_undeclared_imports(setup):
    from haybale_studio.farmhands.authoring import StudioWriteComponentSourceTool

    ctx, registry, identity = setup
    path = Path(identity.folder_path) / "nodes" / "scaled.py"
    thread = _watcher(registry, identity, path, FileEventType.CREATED, path.exists)

    result = _run(
        StudioWriteComponentSourceTool, ctx, source=_SOURCE, library="dst", kind="node", filename="scaled.py"
    )
    thread.join()

    assert result["registration"] == "added"
    assert result["registry_key"] == "dst:node:Scaled"
    assert result["linked_libraries_added"] == ["haybale_src"]
    assert result["undeclared_imports"] == ["haybale-src"]
    assert "haywire share" in result["help"]
    assert read_haybale_toml(Path(identity.folder_path))["linked_libraries"] == [
        "haybale_kept",
        "haybale_src",
    ]
    # The module registered under the refreshed identity.
    assert "haybale_src." in registry._dependency_graph._module_scope_prefixes["haybale_dst.nodes.scaled"]


def test_an_overwrite_is_reported_reloaded(setup):
    from haybale_studio.farmhands.authoring import StudioWriteComponentSourceTool

    ctx, registry, identity = setup
    path = Path(identity.folder_path) / "nodes" / "scaled.py"
    path.write_text(_SOURCE)
    registry.event_dispatcher(FileChangeEvent(str(path), FileEventType.CREATED, identity, time.time()))

    edited = _SOURCE + "\n# edited\n"
    thread = _watcher(registry, identity, path, FileEventType.MODIFIED, lambda: path.read_text() == edited)
    result = _run(StudioWriteComponentSourceTool, ctx, source=edited, registry_key="dst:node:Scaled")
    thread.join()

    assert result["registration"] == "reloaded"
    assert result["registry_key"] == "dst:node:Scaled"
    assert result["linked_libraries_added"] == ["haybale_src"]


def test_a_write_that_fails_to_import_reports_the_ledger_errors(setup, monkeypatch):
    from haybale_studio.farmhands.authoring import StudioWriteComponentSourceTool
    from haywire.core.di import context as di_context
    from haywire.core.errors.ledger import ErrorLedger

    monkeypatch.setattr(di_context, "_error_ledger", ErrorLedger())
    ctx, registry, identity = setup
    path = Path(identity.folder_path) / "nodes" / "broken.py"
    thread = _watcher(registry, identity, path, FileEventType.CREATED, path.exists)

    result = _run(
        StudioWriteComponentSourceTool,
        ctx,
        source="raise RuntimeError('nope')\n",
        library="dst",
        kind="node",
        filename="broken.py",
    )
    thread.join()

    assert result["registration"] == "failed"
    assert result["errors"]
    assert "nope" in result["errors"][0]["detail"]
    assert result["registry_key"] is None
