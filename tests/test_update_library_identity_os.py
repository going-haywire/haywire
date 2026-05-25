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
