"""Manifest readers: `read_manifest` (strict) and `read_manifest_lenient`.

Two postures share one parsing path (Task 2 plan):

* Reading *to report* (`detect_share_drift`, `read_barn_versions`) must
  degrade to `{}` on a bad file — the report should still surface what's
  missing rather than crash.
* Reading *to rewrite* (`apply_drift_fix`, `_build_entry_for_library`) must
  raise, or a corrupt file could get silently overwritten.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from haywire_studio.share import (
    DepDrift,
    InvalidOsDeclarationError,
    ManifestReadError,
    apply_drift_fix,
    read_manifest,
    read_manifest_lenient,
)

pytestmark = pytest.mark.unit


def _make_lib(tmp_path: Path, *, pyproject_text: str | None = None) -> Path:
    """Scaffold a minimal barn library directory with a module package.

    A module dir is included so callers that walk into `detect_deps` /
    `find_module_dir` (e.g. `apply_drift_fix`) don't blow up on a missing
    package — only the pyproject.toml content varies per test.
    """
    lib_dir = tmp_path / "barn" / "haybale-foo"
    pkg_dir = lib_dir / "haybale_foo"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    if pyproject_text is not None:
        (lib_dir / "pyproject.toml").write_text(pyproject_text)
    return lib_dir


def test_lenient_read_returns_empty_on_malformed(tmp_path: Path) -> None:
    lib_dir = _make_lib(tmp_path, pyproject_text="[[[broken")
    assert read_manifest_lenient(lib_dir) == {}


def test_lenient_read_returns_empty_on_unreadable(tmp_path: Path) -> None:
    """No pyproject.toml at all — read_text() raises FileNotFoundError (an
    OSError), which the lenient reader must also absorb."""
    lib_dir = _make_lib(tmp_path, pyproject_text=None)
    assert read_manifest_lenient(lib_dir) == {}


def test_strict_read_raises_on_malformed(tmp_path: Path) -> None:
    lib_dir = _make_lib(tmp_path, pyproject_text="[[[broken")
    with pytest.raises(ManifestReadError):
        read_manifest(lib_dir)


def test_strict_read_raises_on_unreadable(tmp_path: Path) -> None:
    lib_dir = _make_lib(tmp_path, pyproject_text=None)
    with pytest.raises(ManifestReadError):
        read_manifest(lib_dir)


def test_strict_read_raises_on_undeclarable_os_value(tmp_path: Path) -> None:
    """read_manifest absorbs [tool.haywire].os validation: InvalidOsDeclarationError
    is a ManifestReadError subclass, so strict callers see one error family."""
    lib_dir = _make_lib(
        tmp_path,
        pyproject_text=(
            '[project]\nname = "haybale-foo"\nversion = "0.1.0"\n\n[tool.haywire]\nos = ["freebsd"]\n'
        ),
    )
    with pytest.raises(InvalidOsDeclarationError):
        read_manifest(lib_dir)
    # And InvalidOsDeclarationError IS a ManifestReadError — strict callers
    # that only catch the parent still see it.
    with pytest.raises(ManifestReadError):
        read_manifest(lib_dir)


def test_apply_drift_fix_raises_before_writing(tmp_path: Path) -> None:
    """The old guard degraded and then crashed inside set_pyproject_dependencies.
    The strict read must fail BEFORE anything is written."""
    lib_dir = _make_lib(tmp_path, pyproject_text="[[[broken")
    before = (lib_dir / "pyproject.toml").read_text()

    drift = DepDrift(lib_dir=lib_dir, pyproject_missing=["haywire-core"])
    with pytest.raises(ManifestReadError):
        apply_drift_fix(drift)

    after = (lib_dir / "pyproject.toml").read_text()
    assert after == before
