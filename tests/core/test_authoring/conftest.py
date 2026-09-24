"""Fixture packages for the node-authoring pipeline.

``haybale_src`` holds the node classes being cloned: a module declaring one
``@node`` class, and one declaring a family of three with helpers.
``haybale_dst`` is the library a clone is written into.
"""

import sys
import textwrap
from pathlib import Path

import pytest

from haywire.core.authoring import AuthoringTarget
from haywire.core.library.base import BaseLibrary
from haywire.core.library.haybale_toml import HAYBALE_TOML
from haywire.core.library.identity import LibraryIdentity

SINGLE = '''\
"""A module declaring one node."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node

from ..helpers import SCALE


@node(
    label="Single",
    description="Scales a constant.",
    menu="src/single",
    search_tags=["one"],
    registry_id="SingleId",
    deprecation_warning="Going away.",
    node_type=NodeType.DATA,
)
class SingleNode(BaseNode):
    """Outputs SCALE."""

    def init(self):
        from haywire.barn.builtin.types import FLOAT

        from .. import helpers

        self.add(FLOAT.as_outlet("result", label="Result"))
        self._helpers = helpers

    def worker(self, context: ExecutionContext) -> None:
        super(SingleNode, self).worker
        self.out("result", float(SCALE))
'''

MULTI = '''\
"""A module declaring a family of nodes."""

from typing import TYPE_CHECKING

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.barn.builtin.types import FLOAT

if TYPE_CHECKING:
    from haywire.core.node import NodeIdentity

LIMIT = 3
UNUSED = 4


def _helper(value):
    return value


class _Base(BaseNode):
    def init(self):
        self.add(FLOAT.as_outlet("r", label="R"))


@node(label="Parent", menu="src/family", search_tags=["family"], node_type=NodeType.DATA)
class ParentNode(_Base):
    def worker(self, context: ExecutionContext) -> None:
        self.out("r", float(_helper(LIMIT)))


@node(label="Child")
class ChildNode(ParentNode):
    """A child whose menu and tags come from its parent."""

    def worker(self, context: ExecutionContext) -> "ChildNode":
        self.out("r", float(LIMIT))
        return self


@node(label="Template-ish", template=True, hidden=True, menu="src/family")
class TemplatedNode(_Base):
    def worker(self, context: ExecutionContext) -> None:
        self.out("r", 0.0)
'''

BROKEN = """\
from haywire.core.node import BaseNode, NodeType, node

raise RuntimeError("this module cannot be imported")
"""


class DstLibrary(BaseLibrary):
    def register_components(self) -> None:  # pragma: no cover - not exercised here
        pass

    def validate(self) -> bool:  # pragma: no cover - not exercised here
        return True


class FakeLibraries:
    """The installed libraries: no haywire libraries except those named, plus the target's identity."""

    def __init__(self, identity: LibraryIdentity, dists: dict[str, str] | None = None, delegate=None):
        self._identity = identity
        self._dists = dists or {}
        self._delegate = delegate

    def list_names(self) -> list[str]:
        names = list(self._dists)
        if self._delegate is not None:
            names += self._delegate.list_names()
        return names

    def get_library_distribution_name(self, library_id: str) -> str | None:
        if library_id in self._dists:
            return self._dists[library_id]
        if self._delegate is not None:
            return self._delegate.get_library_distribution_name(library_id)
        return None

    def get_library_identity(self, library_registry_name: str) -> LibraryIdentity:
        return self._identity


def _purge(prefix: str) -> None:
    for name in [m for m in sys.modules if m == prefix or m.startswith(prefix + ".")]:
        del sys.modules[name]


@pytest.fixture
def packages(tmp_path, monkeypatch):
    """Write both packages under ``tmp_path`` and put them on ``sys.path``."""
    src = tmp_path / "haybale_src"
    (src / "nodes").mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "pyproject.toml").write_text('[project]\nname = "haybale-src"\n')
    (src / "helpers.py").write_text("SCALE = 2\n")
    (src / "nodes" / "__init__.py").write_text("")
    (src / "nodes" / "single.py").write_text(SINGLE)
    (src / "nodes" / "multi.py").write_text(MULTI)

    dst = tmp_path / "haybale_dst"
    (dst / "nodes").mkdir(parents=True)
    (dst / "__init__.py").write_text("")
    (dst / "pyproject.toml").write_text('[project]\nname = "haybale-dst"\ndependencies = ["haywire-core"]\n')
    (dst / HAYBALE_TOML).write_text(
        textwrap.dedent(
            """\
            name = "dst"
            version = "0.1.0"
            label = "Destination"
            linked_libraries = ["haybale_kept"]
            """
        )
    )

    monkeypatch.syspath_prepend(str(tmp_path))
    _purge("haybale_src")
    _purge("haybale_dst")
    yield src, dst
    _purge("haybale_src")
    _purge("haybale_dst")


@pytest.fixture
def dst_identity(packages) -> LibraryIdentity:
    _src, dst = packages
    return LibraryIdentity(
        name="dst",
        label="Destination",
        folder_path=str(dst),
        module_name="haybale_dst",
        linked_libraries=["haybale_kept"],
    )


@pytest.fixture
def dst_library(dst_identity, monkeypatch) -> DstLibrary:
    """The destination library, installed as ``haybale_dst.Library`` so its nodes key under ``dst``."""
    import importlib

    monkeypatch.setattr(DstLibrary, "class_identity", dst_identity, raising=False)
    package = importlib.import_module("haybale_dst")
    monkeypatch.setattr(package, "Library", DstLibrary, raising=False)
    return DstLibrary(file_path=str(Path(dst_identity.folder_path) / "__init__.py"))


@pytest.fixture
def target(dst_identity) -> AuthoringTarget:
    return AuthoringTarget(
        library_id="dst",
        label="Destination",
        folder=Path(dst_identity.folder_path) / "nodes",
        is_project_library=True,
        is_watched=True,
    )


@pytest.fixture
def libraries(dst_identity) -> FakeLibraries:
    return FakeLibraries(dst_identity)


@pytest.fixture
def src_modules(packages):
    """The imported source modules, as ``(single, multi)``."""
    import importlib

    return importlib.import_module("haybale_src.nodes.single"), importlib.import_module(
        "haybale_src.nodes.multi"
    )
