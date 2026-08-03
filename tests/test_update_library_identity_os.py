"""update_library_identity writes [tool.haywire].os to pyproject.toml per spec §2.1."""

from __future__ import annotations

from pathlib import Path

import pytest
import toml


def _scaffold_minimal_heap(workspace: Path, dist_name: str = "haybale-foo") -> Path:
    """Create a minimal heap library structure that update_library_identity can update."""
    module_name = dist_name.replace("-", "_")
    lib_dir = workspace / "barn" / dist_name
    pkg_dir = lib_dir / module_name
    pkg_dir.mkdir(parents=True)

    (lib_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{dist_name}"\nversion = "0.1.0"\ndescription = "test"\n'
    )
    (pkg_dir / "__init__.py").write_text(
        '"""x."""\n'
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
    (workspace / ".haywire").mkdir()
    (workspace / ".haywire" / "marketplace.toml").write_text(
        f'[[heaps]]\nname = "{dist_name}"\npath = "{lib_dir}"\n'
    )
    return lib_dir


@pytest.mark.unit
def test_apply_os_to_pyproject_writes_section(tmp_path: Path) -> None:
    """The helper writes [tool.haywire].os when given a non-empty list."""
    from haybale_marketplace.library_manager import _apply_os_to_pyproject

    lib_dir = _scaffold_minimal_heap(tmp_path)
    pyproject = lib_dir / "pyproject.toml"

    _apply_os_to_pyproject(pyproject, ["macos", "linux"])

    data = toml.loads(pyproject.read_text())
    assert data["tool"]["haywire"]["os"] == ["macos", "linux"]


@pytest.mark.unit
def test_apply_os_to_pyproject_filters_invalid_values(tmp_path: Path) -> None:
    """Only macos/windows/linux are allowed; 'other' and unknowns are dropped silently."""
    from haybale_marketplace.library_manager import _apply_os_to_pyproject

    lib_dir = _scaffold_minimal_heap(tmp_path)
    pyproject = lib_dir / "pyproject.toml"

    _apply_os_to_pyproject(pyproject, ["macos", "other", "freebsd", "linux"])

    data = toml.loads(pyproject.read_text())
    assert data["tool"]["haywire"]["os"] == ["macos", "linux"]


@pytest.mark.unit
def test_apply_os_to_pyproject_empty_list_removes_section(tmp_path: Path) -> None:
    """An empty list (after filtering) removes [tool.haywire].os entirely."""
    from haybale_marketplace.library_manager import _apply_os_to_pyproject

    lib_dir = _scaffold_minimal_heap(tmp_path)
    pyproject = lib_dir / "pyproject.toml"
    # Pre-populate the field so we can assert it's removed.
    pyproject.write_text(pyproject.read_text() + '\n[tool.haywire]\nos = ["macos"]\n')

    _apply_os_to_pyproject(pyproject, [])

    data = toml.loads(pyproject.read_text())
    assert "haywire" not in data.get("tool", {})


@pytest.mark.unit
def test_apply_os_to_pyproject_all_three_removes_section(tmp_path: Path) -> None:
    """All three platforms = 'all platforms' = absent; remove the key entirely."""
    from haybale_marketplace.library_manager import _apply_os_to_pyproject

    lib_dir = _scaffold_minimal_heap(tmp_path)
    pyproject = lib_dir / "pyproject.toml"

    _apply_os_to_pyproject(pyproject, ["macos", "windows", "linux"])

    data = toml.loads(pyproject.read_text())
    # The spec says selecting all three is equivalent to "all platforms" (absent).
    assert "haywire" not in data.get("tool", {})


@pytest.mark.unit
def test_apply_os_to_pyproject_preserves_other_tool_sections(tmp_path: Path) -> None:
    """Existing [tool.hatch.*] etc. survive the write."""
    from haybale_marketplace.library_manager import _apply_os_to_pyproject

    lib_dir = _scaffold_minimal_heap(tmp_path)
    pyproject = lib_dir / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text() + '\n[tool.hatch.build.targets.wheel]\npackages = ["haybale_foo"]\n'
    )

    _apply_os_to_pyproject(pyproject, ["macos"])

    data = toml.loads(pyproject.read_text())
    assert data["tool"]["haywire"]["os"] == ["macos"]
    assert data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["haybale_foo"]


def test_apply_os_to_pyproject_preserves_comments(tmp_path: Path) -> None:
    """Comments in the author's pyproject.toml survive the write.

    Regression: the write used to round-trip through toml.loads/toml.dumps,
    which rebuilds the document from plain dicts and silently deletes every
    comment. Reported after an uninstall stripped a repo's own pyproject.
    """
    from haybale_marketplace.library_manager import _apply_os_to_pyproject

    lib_dir = _scaffold_minimal_heap(tmp_path)
    pyproject = lib_dir / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text()
        + "\n# Pinned deliberately — do not bump without reading the release notes.\n"
        + '[tool.hatch.build.targets.wheel]\npackages = ["haybale_foo"]\n'
    )

    _apply_os_to_pyproject(pyproject, ["macos"])

    body = pyproject.read_text()
    assert "# Pinned deliberately — do not bump without reading the release notes." in body
    assert toml.loads(body)["tool"]["haywire"]["os"] == ["macos"]


def test_install_writeback_preserves_comments(tmp_path: Path) -> None:
    """Same guarantee on the install path, which edits the *project* file."""
    from haybale_marketplace.library_manager import _write_install_to_pyproject

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "demo"\n'
        "# alpha is pinned until upstream fixes the regression.\n"
        'dependencies = ["alpha~=1.0"]\n'
    )

    _write_install_to_pyproject(pyproject, "haybale-foo", "1.2.3", "pypi", "haybale-foo==1.2.3")

    body = pyproject.read_text()
    assert "# alpha is pinned until upstream fixes the regression." in body
    # A floor, not "~=1.2.3": a ceiling written by the installer is not a policy
    # the author chose, and it later blocks the next minor release.
    assert "haybale-foo>=1.2.3" in body
    # Somebody else's pin is untouched — that ~= IS a deliberate author choice.
    assert "alpha~=1.0" in body


def test_uninstall_writeback_preserves_comments(tmp_path: Path) -> None:
    """And on the uninstall path — the one the bug was reported from."""
    from haybale_marketplace.library_manager import _remove_install_from_pyproject

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "demo"\n'
        "# Keep alpha: the vendored fork is not on PyPI.\n"
        'dependencies = ["alpha~=1.0", "haybale-foo~=1.2.3"]\n'
    )

    _remove_install_from_pyproject(pyproject, "haybale-foo")

    body = pyproject.read_text()
    assert "# Keep alpha: the vendored fork is not on PyPI." in body
    assert "haybale-foo" not in body
    assert "alpha~=1.0" in body


def test_installed_version_reads_dist_info_not_the_running_process(tmp_path: Path) -> None:
    """The version written into pyproject.toml comes from disk, not from
    ``importlib.metadata`` in this process.

    This process imported these packages at startup; an install that happens
    afterwards does not update that cached view unless cache invalidation — which
    leans on a private CPython API behind ``except AttributeError`` — works. A
    stale read here does not stay in memory: it becomes a version pin in the
    user's pyproject.toml. Reading the directory cannot go stale.
    """
    from haybale_marketplace.library_manager import LibraryManager

    site_packages = tmp_path / "lib" / "python3.12" / "site-packages"
    site_packages.mkdir(parents=True)
    (site_packages / "haybale_core-0.0.34.dist-info").mkdir()

    manager = LibraryManager.__new__(LibraryManager)
    manager.venv_path = str(tmp_path)

    # importlib.metadata would report whatever this interpreter loaded; the
    # dist-info on disk says 0.0.34, and that is what must win. Hyphen and
    # underscore spellings both resolve, since installers normalize the dir name.
    assert manager.get_installed_version("haybale-core") == "0.0.34"
    assert manager.get_installed_version("haybale_core") == "0.0.34"


def test_installed_version_returns_none_for_absent_dist(tmp_path: Path) -> None:
    """A name with no dist-info and no in-process metadata resolves to None,
    so the caller writes a bare requirement rather than inventing a version."""
    from haybale_marketplace.library_manager import LibraryManager

    site_packages = tmp_path / "lib" / "python3.12" / "site-packages"
    site_packages.mkdir(parents=True)

    manager = LibraryManager.__new__(LibraryManager)
    manager.venv_path = str(tmp_path)

    assert manager.get_installed_version("haybale-not-installed") is None
