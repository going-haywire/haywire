"""Tests for haywire.core.library.dep_detect.

Each test builds a synthetic mini-library in ``tmp_path`` so we never touch
the real workspace. A ``FakeLibrarySource`` plays the role of the live
LibraryRegistry — that's all detect_deps needs to know what counts as a
haywire library.
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

import pytest

import toml

from haywire.core.library.dep_detect import (
    DetectedDeps,
    HaywireLibrarySource,
    detect_deps,
    find_module_dir,
    set_pyproject_dependencies,
)


# ──────────────────────────────────────────────────────────────────────────────
# Test scaffolding
# ──────────────────────────────────────────────────────────────────────────────


class FakeLibrarySource:
    """Minimal stand-in for LibraryRegistry. Holds id -> distribution name."""

    def __init__(self, registered: dict[str, str] | None = None) -> None:
        self._registered = registered or {}

    def list_names(self) -> list[str]:
        return list(self._registered.keys())

    def get_library_distribution_name(self, library_id: str) -> str | None:
        return self._registered.get(library_id)


def _make_library(
    tmp_path: Path,
    *,
    project_name: str = "haybale-fake",
    module_name: str = "haybale_fake",
    init_body: str = "",
) -> Path:
    """Scaffold a minimal library directory tree.

    Returns the library root (the dir containing pyproject.toml). The module
    package lives at ``<lib_dir>/<module_name>/__init__.py`` with ``init_body``
    as its content.
    """
    lib_dir = tmp_path / project_name
    lib_dir.mkdir()
    (lib_dir / "pyproject.toml").write_text(f'[project]\nname = "{project_name}"\nversion = "0.0.1"\n')
    pkg_dir = lib_dir / module_name
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text(init_body)
    return lib_dir


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_empty_library_returns_empty(tmp_path: Path) -> None:
    lib = _make_library(tmp_path, init_body="")
    result = detect_deps(lib, libraries=FakeLibrarySource())
    assert result == DetectedDeps()


@pytest.mark.unit
def test_stdlib_imports_yield_nothing(tmp_path: Path) -> None:
    lib = _make_library(
        tmp_path,
        init_body="import os\nimport sys\nfrom pathlib import Path\n",
    )
    result = detect_deps(lib, libraries=FakeLibrarySource())
    assert result.library_decorator == []
    assert result.pyproject == []
    assert result.unresolved == []


@pytest.mark.unit
def test_haywire_core_import_emits_haywire_core(tmp_path: Path) -> None:
    lib = _make_library(
        tmp_path,
        init_body="from haywire.core.node.registry import NodeRegistry\n",
    )
    result = detect_deps(lib, libraries=FakeLibrarySource())
    assert result.library_decorator == []
    assert len(result.pyproject) == 1
    assert result.pyproject[0].startswith("haywire-core~=")


@pytest.mark.unit
def test_haywire_ui_import_emits_haywire_studio(tmp_path: Path) -> None:
    lib = _make_library(
        tmp_path,
        init_body="from haywire.ui.elements import elements as hui\n",
    )
    result = detect_deps(lib, libraries=FakeLibrarySource())
    assert result.library_decorator == []
    assert len(result.pyproject) == 1
    assert result.pyproject[0].startswith("haywire-studio~=")


@pytest.mark.unit
def test_bare_haywire_import_emits_haywire_core_conservative(tmp_path: Path) -> None:
    lib = _make_library(tmp_path, init_body="import haywire\n")
    result = detect_deps(lib, libraries=FakeLibrarySource())
    assert any(s.startswith("haywire-core~=") for s in result.pyproject)
    assert not any(s.startswith("haywire-studio") for s in result.pyproject)


@pytest.mark.unit
def test_both_core_and_ui_emit_both_framework_dists(tmp_path: Path) -> None:
    lib = _make_library(
        tmp_path,
        init_body=(
            "from haywire.core.node.registry import NodeRegistry\n"
            "from haywire.ui.elements import elements as hui\n"
        ),
    )
    result = detect_deps(lib, libraries=FakeLibrarySource())
    assert any(s.startswith("haywire-core~=") for s in result.pyproject)
    assert any(s.startswith("haywire-studio~=") for s in result.pyproject)
    # No duplicates.
    assert len(result.pyproject) == 2


@pytest.mark.unit
def test_registered_library_lands_in_both_outputs(tmp_path: Path) -> None:
    """Imports of a *registered* haywire library belong in both
    @library(dependencies=...) and pyproject."""
    lib = _make_library(tmp_path, init_body="from haybale_core import types\n")
    # haybale-core is installed in the dev workspace; the FakeLibrarySource
    # asserts it as a registered library.
    src = FakeLibrarySource({"core": "haybale-core"})
    result = detect_deps(lib, libraries=src)
    assert result.library_decorator == ["haybale_core"]
    assert len(result.pyproject) == 1
    assert result.pyproject[0].startswith("haybale-core~=")


@pytest.mark.unit
def test_unregistered_haybale_shaped_module_is_third_party(tmp_path: Path) -> None:
    """A module whose distribution looks like 'haybale-foo' but is NOT in the
    registry is treated as third-party (pyproject only, >= not ~=)."""
    # We need a real installed dist for the resolver to find something. Pick
    # `toml` (third-party, definitely installed, definitely not a library).
    lib = _make_library(tmp_path, init_body="import toml\n")
    result = detect_deps(lib, libraries=FakeLibrarySource())
    assert result.library_decorator == []
    assert len(result.pyproject) == 1
    spec = result.pyproject[0]
    assert spec.startswith("toml>="), f"expected toml>=..., got {spec!r}"


@pytest.mark.unit
def test_third_party_uses_geq_specifier(tmp_path: Path) -> None:
    """Third-party packages use >= rather than ~= because we don't know
    their compatibility commitments."""
    lib = _make_library(tmp_path, init_body="import pytest\n")
    result = detect_deps(lib, libraries=FakeLibrarySource())
    assert len(result.pyproject) == 1
    spec = result.pyproject[0]
    assert "~=" not in spec
    assert spec.startswith("pytest>=")


@pytest.mark.unit
def test_self_import_is_ignored(tmp_path: Path) -> None:
    """A library importing its own module should not appear in its deps."""
    lib = _make_library(
        tmp_path,
        project_name="haybale-fake",
        module_name="haybale_fake",
        init_body="from haybale_fake import nothing\n",
    )
    result = detect_deps(lib, libraries=FakeLibrarySource())
    assert result.library_decorator == []
    assert result.pyproject == []


@pytest.mark.unit
def test_relative_imports_are_ignored(tmp_path: Path) -> None:
    """`from . import foo` should not be treated as a dependency edge."""
    lib = _make_library(tmp_path, init_body="from . import sibling\n")
    result = detect_deps(lib, libraries=FakeLibrarySource())
    assert result.library_decorator == []
    assert result.pyproject == []
    assert result.unresolved == []


@pytest.mark.unit
def test_version_in_specifier_matches_installed(tmp_path: Path) -> None:
    """The ~= version uses the running-interpreter's installed version of
    the dist, not the library's own version."""
    lib = _make_library(
        tmp_path,
        init_body="from haywire.core.node.registry import NodeRegistry\n",
    )
    result = detect_deps(lib, libraries=FakeLibrarySource())
    installed = importlib.metadata.version("haywire-core")
    assert f"haywire-core~={installed}" in result.pyproject


@pytest.mark.unit
def test_mixed_realistic_tree(tmp_path: Path) -> None:
    """A library importing framework + registered lib + stdlib + third-party
    populates all expected outputs and nothing more."""
    lib = _make_library(
        tmp_path,
        init_body=(
            "import os\n"  # stdlib — dropped
            "from haywire.core.node.registry import NodeRegistry\n"  # haywire-core
            "from haywire.ui.elements import elements as hui\n"  # haywire-studio
            "from haybale_core import types\n"  # registered library
            "import toml\n"  # third-party
        ),
    )
    src = FakeLibrarySource({"core": "haybale-core"})
    result = detect_deps(lib, libraries=src)

    # Decorator: only the registered library.
    assert result.library_decorator == ["haybale_core"]

    # Pyproject: framework x2 + registered lib + third-party = 4 entries.
    pyproj_dists = [spec.split("~=")[0].split(">=")[0] for spec in result.pyproject]
    assert sorted(pyproj_dists) == ["haybale-core", "haywire-core", "haywire-studio", "toml"]

    # No unresolved.
    assert result.unresolved == []


@pytest.mark.unit
def test_find_module_dir_flat_layout(tmp_path: Path) -> None:
    lib = _make_library(tmp_path, module_name="my_pkg")
    assert find_module_dir(lib) == lib / "my_pkg"


@pytest.mark.unit
def test_find_module_dir_src_layout(tmp_path: Path) -> None:
    lib_dir = tmp_path / "haybale-fake"
    lib_dir.mkdir()
    (lib_dir / "pyproject.toml").write_text('[project]\nname = "haybale-fake"\n')
    pkg = lib_dir / "src" / "my_pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    assert find_module_dir(lib_dir) == pkg


@pytest.mark.unit
def test_find_module_dir_skips_dot_and_underscore_dirs(tmp_path: Path) -> None:
    lib_dir = tmp_path / "haybale-fake"
    lib_dir.mkdir()
    (lib_dir / "pyproject.toml").write_text('[project]\nname = "haybale-fake"\n')
    for noise in (".hidden", "__pycache__"):
        d = lib_dir / noise
        d.mkdir()
        (d / "__init__.py").write_text("")
    pkg = lib_dir / "real_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    assert find_module_dir(lib_dir) == pkg


@pytest.mark.unit
def test_protocol_runtime_check_passes_for_fake(tmp_path: Path) -> None:
    """FakeLibrarySource conforms to HaywireLibrarySource at runtime."""
    assert isinstance(FakeLibrarySource(), HaywireLibrarySource)


# ──────────────────────────────────────────────────────────────────────────────
# set_pyproject_dependencies
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_set_pyproject_dependencies_replaces_existing(tmp_path: Path) -> None:
    lib = _make_library(tmp_path)
    pyproject = lib / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "haybale-fake"\nversion = "0.0.1"\ndependencies = ["old-dep>=1.0"]\n'
    )
    set_pyproject_dependencies(lib, ["new-dep~=2.0", "another>=0.1"])

    data = toml.loads(pyproject.read_text())
    assert data["project"]["dependencies"] == ["new-dep~=2.0", "another>=0.1"]
    # Other fields preserved.
    assert data["project"]["name"] == "haybale-fake"
    assert data["project"]["version"] == "0.0.1"


@pytest.mark.unit
def test_set_pyproject_dependencies_creates_section_if_missing(tmp_path: Path) -> None:
    """When [project] has no dependencies key, it should be created."""
    lib = _make_library(tmp_path)
    pyproject = lib / "pyproject.toml"
    pyproject.write_text('[project]\nname = "haybale-fake"\nversion = "0.0.1"\n')

    set_pyproject_dependencies(lib, ["haywire-core~=0.0.1"])

    data = toml.loads(pyproject.read_text())
    assert data["project"]["dependencies"] == ["haywire-core~=0.0.1"]


@pytest.mark.unit
def test_set_pyproject_dependencies_empty_list_clears(tmp_path: Path) -> None:
    """Passing [] removes all dependencies (sets to empty list)."""
    lib = _make_library(tmp_path)
    pyproject = lib / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "haybale-fake"\nversion = "0.0.1"\ndependencies = ["a>=1", "b>=2"]\n'
    )
    set_pyproject_dependencies(lib, [])
    data = toml.loads(pyproject.read_text())
    assert data["project"]["dependencies"] == []


@pytest.mark.unit
def test_set_pyproject_dependencies_preserves_other_sections(tmp_path: Path) -> None:
    """[build-system], [tool.uv.sources], etc. round-trip unchanged."""
    lib = _make_library(tmp_path)
    pyproject = lib / "pyproject.toml"
    pyproject.write_text(
        "[project]\n"
        'name = "haybale-fake"\n'
        'version = "0.0.1"\n'
        'dependencies = ["a>=1"]\n'
        "\n"
        "[build-system]\n"
        'requires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n'
        "\n"
        "[tool.uv.sources]\n"
        'foo = { path = "/some/path", editable = true }\n'
    )
    set_pyproject_dependencies(lib, ["b>=2"])

    data = toml.loads(pyproject.read_text())
    assert data["project"]["dependencies"] == ["b>=2"]
    assert data["build-system"]["build-backend"] == "hatchling.build"
    assert data["tool"]["uv"]["sources"]["foo"]["path"] == "/some/path"


@pytest.mark.unit
def test_set_pyproject_dependencies_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        set_pyproject_dependencies(tmp_path / "nonexistent", ["foo>=1"])


@pytest.mark.unit
def test_set_pyproject_dependencies_raises_on_malformed_toml(tmp_path: Path) -> None:
    """A malformed file should surface the TomlDecodeError, not silently overwrite."""
    lib = _make_library(tmp_path)
    pyproject = lib / "pyproject.toml"
    pyproject.write_text("[[[broken")

    with pytest.raises(toml.TomlDecodeError):
        set_pyproject_dependencies(lib, ["foo>=1"])
