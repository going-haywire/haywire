"""A skin draws and widgets write: no skin module writes the model or redraws a card itself."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_PACKAGES = ("haywire.barn.builtin.skins", "haybale_studio.skins")
_WRITES = (".set_value(", "setattr(", ".redraw()")


def _skin_sources() -> dict[str, str]:
    sources = {}
    for package_name in _PACKAGES:
        package = importlib.import_module(package_name)
        for info in pkgutil.iter_modules(package.__path__):
            path = Path(package.__path__[0]) / f"{info.name}.py"
            if path.exists():
                sources[f"{package_name}.{info.name}"] = path.read_text()
    return sources


def test_the_scan_finds_the_skins() -> None:
    names = _skin_sources()
    assert "haybale_studio.skins.stacked_skin" in names
    assert "haywire.barn.builtin.skins.annotation_skin" in names


@pytest.mark.parametrize("module", sorted(_skin_sources()))
def test_no_skin_writes_the_model(module: str) -> None:
    source = _skin_sources()[module]
    assert [w for w in _WRITES if w in source] == []
