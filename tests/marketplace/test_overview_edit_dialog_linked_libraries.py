"""Tests for the linked_libraries Refresh helper behind the Edit dialog.

Refresh applies the same rule the share pipeline's apply_linked_registrations
uses: union in what the source provably imports, never remove. The editor
stages the result in memory; only Save Changes writes.

Fixtures import `haybale_core` rather than an invented module name: detect_deps
resolves modules through real venv metadata, so an uninstalled name lands in
`unresolved` and never reaches `linked_missing`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from haybale_marketplace.editors._overview_edit_dialog import _refresh_linked_libraries

pytestmark = pytest.mark.unit


class _FakeRegistry:
    """Minimal HaywireLibrarySource stand-in for LibraryRegistry."""

    def __init__(self, dists: dict[str, str]) -> None:
        self._dists = dists  # lib_id -> dist name

    def list_names(self) -> list[str]:
        return list(self._dists.keys())

    def get_library_distribution_name(self, library_id: str) -> str | None:
        return self._dists.get(library_id)


def _make_library(
    tmp_path: Path,
    *,
    module_name: str = "haybale_fake",
    linked_libraries: list[str] | None = None,
    init_body_imports: str = "",
) -> Path:
    """Scaffold a library root: pyproject.toml, plus a package with haybale.toml.

    Returns the LIBRARY ROOT (the pyproject.toml dir) — what detect_share_drift
    and find_module_dir both expect. See "The library-root problem" in the plan.
    """
    lib_dir = tmp_path / "haybale-fake"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text('[project]\nname = "haybale-fake"\nversion = "0.0.1"\n')
    pkg_dir = lib_dir / module_name
    pkg_dir.mkdir()
    linked = linked_libraries or []
    linked_toml = "[" + ", ".join(f'"{n}"' for n in linked) + "]"
    (pkg_dir / "haybale.toml").write_text(
        f'name = "haybale-fake"\nid = "fake"\nlabel = "Fake"\nlinked_libraries = {linked_toml}\n'
    )
    (pkg_dir / "__init__.py").write_text(f"{init_body_imports}\n")
    return lib_dir


def test_refresh_adds_missing_linked_library(tmp_path: Path) -> None:
    lib_dir = _make_library(tmp_path, linked_libraries=[], init_body_imports="import haybale_core\n")

    result = _refresh_linked_libraries(
        lib_dir, current=[], libraries=_FakeRegistry({"core": "haybale-core"})
    )

    assert result.added == ["haybale_core"]
    assert result.merged == ["haybale_core"]
    assert result.no_module_dir is False


def test_refresh_is_idempotent_for_an_already_declared_entry(tmp_path: Path) -> None:
    lib_dir = _make_library(
        tmp_path, linked_libraries=["haybale_core"], init_body_imports="import haybale_core\n"
    )

    result = _refresh_linked_libraries(
        lib_dir, current=["haybale_core"], libraries=_FakeRegistry({"core": "haybale-core"})
    )

    assert result.added == []
    assert result.merged == ["haybale_core"]


def test_refresh_never_removes_an_undetected_entry(tmp_path: Path) -> None:
    """Union, exactly as apply_linked_registrations does it.

    A declared entry the scanner no longer sees is indistinguishable from a
    dynamic import it never could see, so it survives untouched.
    """
    lib_dir = _make_library(tmp_path, linked_libraries=["haybale_core"], init_body_imports="")

    result = _refresh_linked_libraries(
        lib_dir, current=["haybale_core"], libraries=_FakeRegistry({"core": "haybale-core"})
    )

    assert result.added == []
    assert result.merged == ["haybale_core"]


def test_refresh_preserves_entries_the_scan_cannot_prove(tmp_path: Path) -> None:
    """`current` is preserved wholesale, additions merge on top."""
    lib_dir = _make_library(
        tmp_path, linked_libraries=["haybale_hand_added"], init_body_imports="import haybale_core\n"
    )

    result = _refresh_linked_libraries(
        lib_dir, current=["haybale_hand_added"], libraries=_FakeRegistry({"core": "haybale-core"})
    )

    assert result.added == ["haybale_core"]
    assert result.merged == ["haybale_core", "haybale_hand_added"]


def test_refresh_reports_no_module_dir_when_source_is_missing(tmp_path: Path) -> None:
    lib_dir = tmp_path / "haybale-empty"
    lib_dir.mkdir()
    (lib_dir / "pyproject.toml").write_text('[project]\nname = "haybale-empty"\nversion = "0.0.1"\n')

    result = _refresh_linked_libraries(lib_dir, current=[], libraries=_FakeRegistry({}))

    assert result.no_module_dir is True
    assert result.added == []
