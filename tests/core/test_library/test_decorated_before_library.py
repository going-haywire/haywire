"""``@library`` refuses a package whose components were decorated before its ``Library`` class."""

import importlib
import sys
from pathlib import Path
from typing import Iterator

import pytest

_PACKAGE = "haybale_early_probe"

_TOML = 'name = "haybale-early-probe"\nversion = "0.0.1"\n'

_STATE = """\
from haywire.core.state import AppState
from haywire.core.state.decorator import state


@state()
class ProbeState(AppState):
    pass
"""

_LIBRARY = """\
from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library


@library()
class Library(BaseLibrary):
    def register_components(self):
        pass

    def validate(self) -> bool:
        return True
"""

_IMPORT_STATE = f"from {_PACKAGE}.probe_state import ProbeState  # noqa: E402\n"


@pytest.fixture
def make_package(tmp_path: Path) -> Iterator:
    """Write the probe package with ``__init__`` body ``init``; drop it from ``sys.modules`` after."""

    def make(init: str) -> None:
        package_dir = tmp_path / _PACKAGE
        package_dir.mkdir()
        (package_dir / "haybale.toml").write_text(_TOML)
        (package_dir / "probe_state.py").write_text(_STATE)
        (package_dir / "__init__.py").write_text(init)

    sys.path.insert(0, str(tmp_path))
    yield make
    sys.path.remove(str(tmp_path))
    for name in [n for n in sys.modules if n == _PACKAGE or n.startswith(f"{_PACKAGE}.")]:
        del sys.modules[name]


@pytest.mark.unit
def test_component_imported_above_library_raises(make_package) -> None:
    make_package(_IMPORT_STATE + _LIBRARY)
    with pytest.raises(ImportError, match=rf"{_PACKAGE}\.probe_state\.ProbeState was decorated before"):
        importlib.import_module(_PACKAGE)


@pytest.mark.unit
def test_component_imported_below_library_is_keyed_to_it(make_package) -> None:
    make_package(_LIBRARY + _IMPORT_STATE)
    package = importlib.import_module(_PACKAGE)
    assert package.ProbeState.class_identity.registry_key == "haybale-early-probe:state:ProbeState"
