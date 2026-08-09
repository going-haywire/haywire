"""A library must not register its own root as a component folder.

Folder mappings have priority *and* exclusivity over root fallbacks in the
watcher: if any folder mapping matches a path, the fallbacks are never
consulted. A library claiming its own root would therefore match everything and
starve whatever rides the fallback — including its own haybale.toml refresh,
which would just stop firing with nothing to show for it.

The convention holds across every library today (they all register subfolders).
The assertion turns a silent future breakage into an error at registration.
"""

from pathlib import Path

import pytest

from haywire.core.library.base import BaseLibrary
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import BaseRegistry


class _Registry(BaseRegistry):
    def _class_filter(self, cls) -> bool:  # pragma: no cover - not exercised here
        return False

    def _register_class(self, cls, library_identity=None):  # pragma: no cover
        return None

    def _unregister_class(self, registry_key):  # pragma: no cover
        return None

    def event_dispatcher(self, event):  # pragma: no cover
        return None


class _Lib(BaseLibrary):
    def register_components(self) -> None:  # pragma: no cover - not exercised here
        pass

    def validate(self) -> bool:  # pragma: no cover - not exercised here
        return True


@pytest.fixture
def library(tmp_path: Path) -> _Lib:
    _Lib.class_identity = LibraryIdentity(
        id="demo",
        label="Demo",
        folder_path=str(tmp_path),
        module_name="haybale_demo",
    )
    lib = _Lib(file_path=str(tmp_path / "__init__.py"))
    lib.add_registry(_Registry, _Registry())
    return lib


@pytest.mark.unit
@pytest.mark.core
def test_registering_the_library_root_raises(library: _Lib, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot register the library root"):
        library.add_folder_to_registry(str(tmp_path), _Registry)


@pytest.mark.unit
@pytest.mark.core
def test_the_root_is_recognised_through_a_non_normalised_path(library: _Lib, tmp_path: Path) -> None:
    """`base_path / "nodes" / ".."` is still the root."""
    with pytest.raises(ValueError, match="cannot register the library root"):
        library.add_folder_to_registry(str(tmp_path / "nodes" / ".."), _Registry)


@pytest.mark.unit
@pytest.mark.core
def test_registering_a_subfolder_is_fine(library: _Lib, tmp_path: Path) -> None:
    nodes = tmp_path / "nodes"
    nodes.mkdir()

    library.add_folder_to_registry(str(nodes), _Registry)

    assert library._registry_folders[_Registry] == (str(nodes), None)
