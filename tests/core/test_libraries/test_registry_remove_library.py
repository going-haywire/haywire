"""Tests for LibraryRegistry.remove_library() sys.modules ejection
and find_library_by_distribution_name()."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

from haywire.core.library.registry import LibraryRegistry
from haywire.core.library.install_type import InstallType


def _make_lib_mock(library_id: str) -> MagicMock:
    lib = MagicMock()
    lib.identity.id = library_id
    lib.identity.label = library_id
    lib.enabled = True
    return lib


def _register_fake(reg: LibraryRegistry, library_id: str, source_path: str, dist_name: str) -> None:
    """Inject a fake library directly into registry internals."""
    lib = _make_lib_mock(library_id)
    reg._libraries[library_id] = lib
    reg._library_sources[library_id] = source_path
    reg._library_install_types[library_id] = InstallType.REGULAR
    reg._library_distribution_names[library_id] = dist_name


@pytest.mark.unit
def test_remove_library_ejects_top_level_module(tmp_path):
    """remove_library() must delete the top-level module from sys.modules."""
    reg = LibraryRegistry()
    source = str(tmp_path / "haybale_core")
    _register_fake(reg, "haybale_core", source, "haybale-core")

    # Plant a fake module in sys.modules
    fake_mod = types.ModuleType("haybale_core")
    sys.modules["haybale_core"] = fake_mod
    try:
        reg.remove_library("haybale_core")
        assert "haybale_core" not in sys.modules
    finally:
        sys.modules.pop("haybale_core", None)


@pytest.mark.unit
def test_remove_library_ejects_submodules(tmp_path):
    """remove_library() must also eject submodules (haybale_core.nodes.blur etc.)."""
    reg = LibraryRegistry()
    source = str(tmp_path / "haybale_core")
    _register_fake(reg, "haybale_core", source, "haybale-core")

    sys.modules["haybale_core"] = types.ModuleType("haybale_core")
    sys.modules["haybale_core.nodes"] = types.ModuleType("haybale_core.nodes")
    sys.modules["haybale_core.nodes.blur"] = types.ModuleType("haybale_core.nodes.blur")
    # A different package that shares a prefix — must NOT be ejected
    sys.modules["haybale_core_extra"] = types.ModuleType("haybale_core_extra")
    try:
        reg.remove_library("haybale_core")
        assert "haybale_core" not in sys.modules
        assert "haybale_core.nodes" not in sys.modules
        assert "haybale_core.nodes.blur" not in sys.modules
        assert "haybale_core_extra" in sys.modules  # unrelated — untouched
    finally:
        for k in ["haybale_core", "haybale_core.nodes", "haybale_core.nodes.blur", "haybale_core_extra"]:
            sys.modules.pop(k, None)


@pytest.mark.unit
def test_remove_library_no_source_path_skips_ejection(tmp_path):
    """remove_library() must not crash when the library has no recorded source path."""
    reg = LibraryRegistry()
    lib = _make_lib_mock("haybale_core")
    reg._libraries["haybale_core"] = lib
    # Intentionally no entry in _library_sources
    reg._library_distribution_names["haybale_core"] = "haybale-core"
    reg._library_install_types["haybale_core"] = InstallType.REGULAR

    sys.modules["haybale_core"] = types.ModuleType("haybale_core")
    try:
        result = reg.remove_library("haybale_core")
        assert result is True
        # Module may or may not be ejected — no crash is the requirement
    finally:
        sys.modules.pop("haybale_core", None)


@pytest.mark.unit
def test_find_library_by_distribution_name_returns_id(tmp_path):
    """find_library_by_distribution_name() must return the library_id for a known dist."""
    reg = LibraryRegistry()
    _register_fake(reg, "haybale_core", str(tmp_path), "haybale-core")
    assert reg.find_library_by_distribution_name("haybale-core") == "haybale_core"


@pytest.mark.unit
def test_find_library_by_distribution_name_unknown_returns_none():
    """find_library_by_distribution_name() must return None for unknown dist names."""
    reg = LibraryRegistry()
    assert reg.find_library_by_distribution_name("haybale-unknown") is None
