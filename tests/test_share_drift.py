"""Tests for the dependency-drift gate in `haywire share` (piece 3).

The gate detects when a library's pyproject.toml or @library decorator
falls out of sync with what its source actually imports. It surfaces
this at share time so the published library doesn't ship a misleading
manifest.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import toml

from haywire.core.library.dep_detect import EntryPointLibrarySource
from haywire_studio.share import (
    DepDrift,
    DriftError,
    _format_drift_report,
    apply_drift_fix,
    detect_share_drift,
    share_save_repo,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _make_library(
    tmp_path: Path,
    *,
    project_name: str = "haybale-fake",
    module_name: str = "haybale_fake",
    pyproject_deps: list[str] | None = None,
    decorator_deps: list[str] | None = None,
    init_body_imports: str = "",
) -> Path:
    """Scaffold a fake library with explicit pyproject + decorator + imports.

    Returns the library root path.
    """
    lib_dir = tmp_path / project_name
    lib_dir.mkdir(parents=True)
    deps_toml = ""
    if pyproject_deps is not None:
        deps_toml = "dependencies = [" + ", ".join(f'"{d}"' for d in pyproject_deps) + "]\n"
    (lib_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{project_name}"\nversion = "0.0.1"\n{deps_toml}'
    )
    pkg_dir = lib_dir / module_name
    pkg_dir.mkdir()
    deps_repr = repr(decorator_deps) if decorator_deps is not None else "[]"
    init_content = (
        "@library(\n"
        "    label='Fake',\n"
        "    id='fake',\n"
        f"    dependencies={deps_repr},\n"
        "    file_watcher=False,\n"
        ")\n"
        "class Library:\n"
        "    pass\n\n"
        f"{init_body_imports}\n"
    )
    (pkg_dir / "__init__.py").write_text(init_content)
    return lib_dir


# ──────────────────────────────────────────────────────────────────────────────
# DepDrift / detect_share_drift
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_drift_empty_when_no_imports(tmp_path: Path) -> None:
    lib = _make_library(tmp_path, init_body_imports="")
    drift = detect_share_drift(lib)
    assert not drift.has_drift
    assert drift.unresolved == []


@pytest.mark.unit
def test_drift_when_pyproject_missing_haywire_core(tmp_path: Path) -> None:
    """Source imports haywire.core.X but pyproject.toml has no deps — drift."""
    lib = _make_library(
        tmp_path,
        pyproject_deps=[],  # explicit: no declared deps
        init_body_imports="from haywire.core.node.registry import NodeRegistry\n",
    )
    drift = detect_share_drift(lib)
    assert drift.has_drift
    # Bare names — _strip_specifier drops version operators.
    assert "haywire-core" in drift.pyproject_missing


@pytest.mark.unit
def test_drift_decorator_missing_registered_library(tmp_path: Path) -> None:
    """Source imports a registered haywire library but the decorator
    omits it — drift on the decorator side, not pyproject."""
    lib = _make_library(
        tmp_path,
        pyproject_deps=["haybale-core~=0.0.1"],
        decorator_deps=[],
        init_body_imports="from haybale_core import types\n",
    )
    drift = detect_share_drift(lib)
    # haybale_core is a registered library (real entry point in dev workspace)
    # so it should appear in the decorator-missing list.
    assert "haybale_core" in drift.decorator_missing


@pytest.mark.unit
def test_drift_no_drift_when_everything_declared(tmp_path: Path) -> None:
    """All imports declared in both places — no drift."""
    lib = _make_library(
        tmp_path,
        pyproject_deps=["haywire-core~=0.0.1", "haybale-core~=0.0.1"],
        decorator_deps=["haybale_core"],
        init_body_imports=(
            "from haywire.core.node.registry import NodeRegistry\nfrom haybale_core import types\n"
        ),
    )
    drift = detect_share_drift(lib)
    assert not drift.has_drift


@pytest.mark.unit
def test_drift_extra_declarations_dont_count_as_drift(tmp_path: Path) -> None:
    """Declared but unused deps must NOT be flagged: false positives would
    block users with optional or transitive deps."""
    lib = _make_library(
        tmp_path,
        pyproject_deps=["haywire-core~=0.0.1", "numpy>=1.0"],  # numpy is not imported
        init_body_imports="from haywire.core.node.registry import NodeRegistry\n",
    )
    drift = detect_share_drift(lib)
    assert not drift.has_drift


@pytest.mark.unit
def test_drift_handles_malformed_pyproject_gracefully(tmp_path: Path) -> None:
    """A malformed pyproject.toml should NOT crash detect_share_drift; it
    should treat declarations as empty so the drift report still surfaces."""
    lib = _make_library(
        tmp_path,
        init_body_imports="from haywire.core.node.registry import NodeRegistry\n",
    )
    # Stomp the pyproject after creation.
    (lib / "pyproject.toml").write_text("[[[broken")
    drift = detect_share_drift(lib)
    assert drift.has_drift
    assert "haywire-core" in drift.pyproject_missing


# ──────────────────────────────────────────────────────────────────────────────
# _format_drift_report
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_format_drift_report_includes_library_name(tmp_path: Path) -> None:
    drift = DepDrift(
        lib_dir=tmp_path / "haybale-fake",
        pyproject_missing=["haywire-core"],
    )
    report = _format_drift_report(drift)
    assert "haybale-fake" in report
    assert "haywire-core" in report


@pytest.mark.unit
def test_format_drift_report_groups_pyproject_decorator_unresolved(tmp_path: Path) -> None:
    drift = DepDrift(
        lib_dir=tmp_path / "haybale-fake",
        pyproject_missing=["haywire-core"],
        decorator_missing=["haybale_core"],
        unresolved=["mystery"],
    )
    report = _format_drift_report(drift)
    # Pyproject section appears before decorator section appears before unresolved.
    assert report.index("pyproject") < report.index("@library")
    assert report.index("@library") < report.index("Unresolved")


# ──────────────────────────────────────────────────────────────────────────────
# apply_drift_fix
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_apply_drift_fix_writes_missing_pyproject_deps(tmp_path: Path) -> None:
    """After apply, the library's pyproject.toml contains the missing deps."""
    lib = _make_library(
        tmp_path,
        pyproject_deps=[],
        init_body_imports="from haywire.core.node.registry import NodeRegistry\n",
    )
    drift = detect_share_drift(lib)
    assert drift.has_drift  # sanity

    apply_drift_fix(drift)

    data = toml.loads((lib / "pyproject.toml").read_text())
    deps = data["project"]["dependencies"]
    assert any(d.startswith("haywire-core") for d in deps)


@pytest.mark.unit
def test_apply_drift_fix_preserves_existing_pyproject_deps(tmp_path: Path) -> None:
    """Existing declarations (even with custom version pins) are preserved
    on the union — apply only adds, never removes or overwrites."""
    lib = _make_library(
        tmp_path,
        pyproject_deps=["numpy>=1.25"],  # unused but declared
        init_body_imports="from haywire.core.node.registry import NodeRegistry\n",
    )
    drift = detect_share_drift(lib)
    apply_drift_fix(drift)

    data = toml.loads((lib / "pyproject.toml").read_text())
    deps = data["project"]["dependencies"]
    assert "numpy>=1.25" in deps
    assert any(d.startswith("haywire-core") for d in deps)


@pytest.mark.unit
def test_apply_drift_fix_idempotent(tmp_path: Path) -> None:
    """Running apply twice produces the same pyproject."""
    lib = _make_library(
        tmp_path,
        pyproject_deps=[],
        init_body_imports="from haywire.core.node.registry import NodeRegistry\n",
    )
    apply_drift_fix(detect_share_drift(lib))
    first = (lib / "pyproject.toml").read_text()
    apply_drift_fix(detect_share_drift(lib))
    second = (lib / "pyproject.toml").read_text()
    assert first == second


@pytest.mark.unit
def test_apply_drift_fix_no_op_when_no_drift(tmp_path: Path) -> None:
    """apply_drift_fix on a clean DepDrift is a no-op."""
    lib = _make_library(tmp_path)
    drift = DepDrift(lib_dir=lib)
    apply_drift_fix(drift)  # must not raise
    assert toml.loads((lib / "pyproject.toml").read_text())["project"]["name"] == "haybale-fake"


# ──────────────────────────────────────────────────────────────────────────────
# share_save_repo gate integration
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_share_save_strict_raises_drifterror(tmp_path: Path) -> None:
    """A repo with one drifty library + --strict raises DriftError before writing."""
    repo = tmp_path / "fake-repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    lib = _make_library(
        repo / "barn",
        pyproject_deps=[],
        init_body_imports="from haywire.core.node.registry import NodeRegistry\n",
    )
    assert lib.exists()  # sanity

    with pytest.raises(DriftError) as exc_info:
        share_save_repo(repo, strict=True)

    assert "haywire-core" in str(exc_info.value)
    # Output file must NOT exist on strict failure.
    assert not (repo / "marketstall.toml").exists()


@pytest.mark.unit
def test_share_save_fix_auto_corrects_then_emits(tmp_path: Path) -> None:
    """--fix updates the library's pyproject in place, then emits the marketstall."""
    repo = tmp_path / "fake-repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    lib = _make_library(
        repo / "barn",
        pyproject_deps=[],
        init_body_imports="from haywire.core.node.registry import NodeRegistry\n",
    )

    share_save_repo(repo, fix=True)

    # Marketstall written.
    assert (repo / "marketstall.toml").is_file()
    # Library's pyproject now declares haywire-core.
    data = toml.loads((lib / "pyproject.toml").read_text())
    assert any(d.startswith("haywire-core") for d in data["project"]["dependencies"])


@pytest.mark.unit
def test_share_save_warn_only_still_emits(tmp_path: Path) -> None:
    """Default mode (no flags): drift is warned about but the marketstall still writes."""
    repo = tmp_path / "fake-repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    lib = _make_library(
        repo / "barn",
        pyproject_deps=[],
        init_body_imports="from haywire.core.node.registry import NodeRegistry\n",
    )

    share_save_repo(repo)

    assert (repo / "marketstall.toml").is_file()
    # Library's pyproject is unchanged.
    data = toml.loads((lib / "pyproject.toml").read_text())
    assert data["project"]["dependencies"] == []


# ──────────────────────────────────────────────────────────────────────────────
# EntryPointLibrarySource sanity
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_entry_point_source_finds_dev_workspace_libraries() -> None:
    """In the dev venv, EntryPointLibrarySource should resolve haybale-core
    and haybale-studio (their entry points are registered)."""
    src = EntryPointLibrarySource()
    names = src.list_names()
    # Names depend on actual entry-point declarations — match by distribution name.
    dists = {src.get_library_distribution_name(n) for n in names}
    assert "haybale-core" in dists
    assert "haybale-studio" in dists
