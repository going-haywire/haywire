"""haywire share reads os from the decorator and validates it per spec §2.1.

[tool.haywire].os is no longer a carrier the producer reads, but it is still
read by strip_undeclarable_os_values — the repair path for a library that
declares it — so the strip tests below still write that key.
"""

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


def _make_lib(
    tmp_path: Path, *, os_decl: list[str] | None = None, decorator_os: list[str] | None = None
) -> Path:
    """Scaffold a minimal barn library.

    *decorator_os* is the authored carrier the producer reads; *os_decl* writes
    the superseded ``[tool.haywire].os`` key, which only the strip_os repair
    path still reads.
    """
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    pkg = lib_dir / "haybale_foo"
    pkg.mkdir()
    os_kwarg = f"         os={decorator_os!r},\n" if decorator_os is not None else ""
    (pkg / "__init__.py").write_text(
        '"""Foo."""\n'
        "from haywire.core.library.base import BaseLibrary\n"
        "from haywire.core.library.decorator import library\n"
        "\n"
        '@library(label="Foo", id="foo",\n'
        f"{os_kwarg}"
        "         linked_libraries=[], file_watcher=False)\n"
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
    """The decorator's declared os is copied into the haybale entry."""
    from haywire.core.publishing.marketstall import _build_entry_for_library

    lib_dir = _make_lib(tmp_path, decorator_os=["macos", "linux"])
    entry = _build_entry_for_library(lib_dir)
    assert entry is not None
    assert entry["os"] == ["macos", "linux"]


@pytest.mark.unit
def test_share_omits_os_when_absent(tmp_path: Path) -> None:
    """An undeclared os means absent from the haybale entry (= all platforms)."""
    from haywire.core.publishing.marketstall import _build_entry_for_library

    lib_dir = _make_lib(tmp_path, os_decl=None)
    entry = _build_entry_for_library(lib_dir)
    assert entry is not None
    assert "os" not in entry  # to_dict() omits empty lists


@pytest.mark.unit
def test_share_rejects_other_as_declaration(tmp_path: Path) -> None:
    """Per §2.1: 'other' is a runtime sentinel, not declarable."""
    from haywire.core.publishing import InvalidOsDeclarationError
    from haywire.core.publishing.marketstall import _build_entry_for_library

    lib_dir = _make_lib(tmp_path, os_decl=["macos", "other"])
    with pytest.raises(InvalidOsDeclarationError) as exc_info:
        _build_entry_for_library(lib_dir)
    assert "other" in str(exc_info.value)
    assert "macos, windows, linux" in str(exc_info.value)


@pytest.mark.unit
def test_share_rejects_unknown_value(tmp_path: Path) -> None:
    """Per §2.1: any value not in {macos, windows, linux} is rejected."""
    from haywire.core.publishing import InvalidOsDeclarationError
    from haywire.core.publishing.marketstall import _build_entry_for_library

    lib_dir = _make_lib(tmp_path, os_decl=["freebsd"])
    with pytest.raises(InvalidOsDeclarationError):
        _build_entry_for_library(lib_dir)


@pytest.mark.unit
def test_share_accepts_all_three_declarable_values(tmp_path: Path) -> None:
    from haywire.core.publishing.marketstall import _build_entry_for_library

    lib_dir = _make_lib(tmp_path, decorator_os=["macos", "windows", "linux"])
    entry = _build_entry_for_library(lib_dir)
    assert entry is not None
    assert entry["os"] == ["macos", "windows", "linux"]


# ── strip_undeclarable_os_values (Task 2: fix_id="strip_os") ───────────────


@pytest.mark.unit
def test_strip_removes_invalid_value_keeping_declarable_ones(tmp_path: Path) -> None:
    from haywire.core.publishing import strip_undeclarable_os_values

    lib_dir = _make_lib(tmp_path, os_decl=["macos", "other"])
    removed = strip_undeclarable_os_values(lib_dir)

    assert removed == ["other"]
    text = (lib_dir / "pyproject.toml").read_text()
    assert 'os = ["macos"]' in text


@pytest.mark.unit
def test_strip_corrects_near_miss_osx_to_macos(tmp_path: Path) -> None:
    from haywire.core.publishing import strip_undeclarable_os_values

    lib_dir = _make_lib(tmp_path, os_decl=["osx"])
    removed = strip_undeclarable_os_values(lib_dir)

    assert removed == ["osx"]
    text = (lib_dir / "pyproject.toml").read_text()
    assert 'os = ["macos"]' in text


@pytest.mark.unit
@pytest.mark.parametrize("value", ["osx", "darwin", "mac"])
def test_strip_maps_all_macos_near_misses(tmp_path: Path, value: str) -> None:
    from haywire.core.publishing import strip_undeclarable_os_values

    lib_dir = _make_lib(tmp_path, os_decl=[value])
    strip_undeclarable_os_values(lib_dir)
    text = (lib_dir / "pyproject.toml").read_text()
    assert 'os = ["macos"]' in text


@pytest.mark.unit
@pytest.mark.parametrize("value", ["win", "win32", "nt"])
def test_strip_maps_all_windows_near_misses(tmp_path: Path, value: str) -> None:
    from haywire.core.publishing import strip_undeclarable_os_values

    lib_dir = _make_lib(tmp_path, os_decl=[value])
    strip_undeclarable_os_values(lib_dir)
    text = (lib_dir / "pyproject.toml").read_text()
    assert 'os = ["windows"]' in text


@pytest.mark.unit
def test_strip_drops_unmapped_unknown_value_without_guessing(tmp_path: Path) -> None:
    from haywire.core.publishing import strip_undeclarable_os_values

    lib_dir = _make_lib(tmp_path, os_decl=["macos", "freebsd"])
    removed = strip_undeclarable_os_values(lib_dir)

    assert removed == ["freebsd"]
    text = (lib_dir / "pyproject.toml").read_text()
    assert 'os = ["macos"]' in text


@pytest.mark.unit
def test_strip_preserves_comments_and_key_order(tmp_path: Path) -> None:
    from haywire.core.publishing import strip_undeclarable_os_values

    lib_dir = _make_lib(tmp_path, os_decl=None)
    pyproject_path = lib_dir / "pyproject.toml"
    original = pyproject_path.read_text()
    original += (
        "\n[tool.haywire]\n"
        "# a comment that must survive\n"
        'os = ["macos", "other", "windows"]\n'
        "other_key = 1\n"
    )
    pyproject_path.write_text(original)

    removed = strip_undeclarable_os_values(lib_dir)

    assert removed == ["other"]
    text = pyproject_path.read_text()
    assert "# a comment that must survive" in text
    assert 'os = ["macos", "windows"]' in text
    # key order preserved: other_key still follows os on its own line
    lines = text.splitlines()
    os_idx = next(i for i, line in enumerate(lines) if line.startswith("os ="))
    other_key_idx = next(i for i, line in enumerate(lines) if line.startswith("other_key"))
    assert other_key_idx == os_idx + 1


@pytest.mark.unit
def test_strip_dedups_near_miss_preceding_its_declarable_target(tmp_path: Path) -> None:
    """Order shouldn't matter: a near-miss listed BEFORE the already-declarable
    value it maps to must not produce a duplicate (regression for a bug where
    dedup only checked the running prefix, not the final result)."""
    from haywire.core.publishing import strip_undeclarable_os_values

    lib_dir = _make_lib(tmp_path, os_decl=["osx", "macos"])
    removed = strip_undeclarable_os_values(lib_dir)

    assert removed == ["osx"]
    text = (lib_dir / "pyproject.toml").read_text()
    assert 'os = ["macos"]' in text


@pytest.mark.unit
def test_strip_returns_empty_list_when_nothing_invalid(tmp_path: Path) -> None:
    from haywire.core.publishing import strip_undeclarable_os_values

    lib_dir = _make_lib(tmp_path, os_decl=["macos", "linux"])
    removed = strip_undeclarable_os_values(lib_dir)

    assert removed == []
    text = (lib_dir / "pyproject.toml").read_text()
    assert 'os = ["macos", "linux"]' in text


# ── describe_os_fix (fix_label computation) ─────────────────────────────────


@pytest.mark.unit
def test_describe_os_fix_label_when_all_values_map_to_macos() -> None:
    from haywire.core.publishing import describe_os_fix

    assert describe_os_fix(["osx", "darwin"]) == "Correct to macos"


@pytest.mark.unit
def test_describe_os_fix_label_when_all_values_map_to_windows() -> None:
    from haywire.core.publishing import describe_os_fix

    assert describe_os_fix(["win", "nt"]) == "Correct to windows"


@pytest.mark.unit
def test_describe_os_fix_label_generic_when_values_are_mixed() -> None:
    from haywire.core.publishing import describe_os_fix

    assert describe_os_fix(["osx", "freebsd"]) == "Remove invalid values"


@pytest.mark.unit
def test_describe_os_fix_label_generic_when_unmapped() -> None:
    from haywire.core.publishing import describe_os_fix

    assert describe_os_fix(["other"]) == "Remove invalid values"
