"""haywire share reads and validates [tool.haywire].os per spec §2.1."""

from __future__ import annotations

from pathlib import Path

import pytest


_SHIPPABLE_PYPROJECT = """[project]
name = "haybale-foo"
version = "0.1.0"
description = "x"

[tool.hatch.build.targets.wheel]
packages = ["haybale_foo"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""


def _make_lib(tmp_path: Path, *, os_decl: list[str] | None = None) -> Path:
    """Scaffold a minimal barn library with optional [tool.haywire].os declaration."""
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    pkg = lib_dir / "haybale_foo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        '"""Foo."""\n'
        "from haywire.core.library.base import BaseLibrary\n"
        "from haywire.core.library.decorator import library\n"
        "\n"
        '@library(label="Foo", id="foo", version="0.1.0", description="x",\n'
        '         url="", help_url="", author="", author_url="",\n'
        "         dependencies=[], tags=[], file_watcher=False)\n"
        "class Library(BaseLibrary):\n"
        "    def register_components(self): pass\n"
        "    def validate(self) -> bool: return True\n"
    )
    pyproject = _SHIPPABLE_PYPROJECT
    if os_decl is not None:
        os_inline = ", ".join(f'"{x}"' for x in os_decl)
        pyproject += f"\n[tool.haywire]\nos = [{os_inline}]\n"
    (lib_dir / "pyproject.toml").write_text(pyproject)
    (tmp_path / ".git").mkdir()  # so _find_git_root succeeds
    return lib_dir


@pytest.mark.unit
def test_share_reads_os_field(tmp_path: Path) -> None:
    """Declared [tool.haywire].os is copied into the haybale entry."""
    from haywire_studio.share import _build_entry_for_library

    lib_dir = _make_lib(tmp_path, os_decl=["macos", "linux"])
    entry = _build_entry_for_library(lib_dir)
    assert entry is not None
    assert entry["os"] == ["macos", "linux"]


@pytest.mark.unit
def test_share_omits_os_when_absent(tmp_path: Path) -> None:
    """Absent [tool.haywire].os means absent from the haybale entry (= all platforms)."""
    from haywire_studio.share import _build_entry_for_library

    lib_dir = _make_lib(tmp_path, os_decl=None)
    entry = _build_entry_for_library(lib_dir)
    assert entry is not None
    assert "os" not in entry  # to_dict() omits empty lists


@pytest.mark.unit
def test_share_rejects_other_as_declaration(tmp_path: Path) -> None:
    """Per §2.1: 'other' is a runtime sentinel, not declarable."""
    from haywire_studio.share import InvalidOsDeclarationError, _build_entry_for_library

    lib_dir = _make_lib(tmp_path, os_decl=["macos", "other"])
    with pytest.raises(InvalidOsDeclarationError) as exc_info:
        _build_entry_for_library(lib_dir)
    assert "other" in str(exc_info.value)
    assert "macos, windows, linux" in str(exc_info.value)


@pytest.mark.unit
def test_share_rejects_unknown_value(tmp_path: Path) -> None:
    """Per §2.1: any value not in {macos, windows, linux} is rejected."""
    from haywire_studio.share import InvalidOsDeclarationError, _build_entry_for_library

    lib_dir = _make_lib(tmp_path, os_decl=["freebsd"])
    with pytest.raises(InvalidOsDeclarationError):
        _build_entry_for_library(lib_dir)


@pytest.mark.unit
def test_share_accepts_all_three_declarable_values(tmp_path: Path) -> None:
    from haywire_studio.share import _build_entry_for_library

    lib_dir = _make_lib(tmp_path, os_decl=["macos", "windows", "linux"])
    entry = _build_entry_for_library(lib_dir)
    assert entry is not None
    assert entry["os"] == ["macos", "windows", "linux"]
