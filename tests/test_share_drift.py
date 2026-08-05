"""Tests for the dependency-drift gate in `haywire share` (piece 3).

The gate detects when a library's pyproject.toml or @library decorator
falls out of sync with what its source actually imports. It surfaces
this at share time so the published library doesn't ship a misleading
manifest.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from haywire.core.library.dep_detect import EntryPointLibrarySource
from haywire_studio.packaging.share import (
    DepDrift,
    _format_drift_report,
    detect_share_drift,
)

# One venv metadata scan for the whole module (see tests/conftest.py).
pytestmark = pytest.mark.usefixtures("cached_packages_distributions")


class _FakeLibrarySource:
    """Minimal HaywireLibrarySource for testing union/lag with a controlled set
    of registered dists. Avoids depending on the dev workspace's real entry
    points."""

    def __init__(self, dists: list[str]) -> None:
        # entry-point name → dist name. Tests only need the dist set, so use
        # the dist name as both key and value.
        self._map = {d: d for d in dists}

    def list_names(self) -> list[str]:
        return list(self._map.keys())

    def get_library_distribution_name(self, library_id: str) -> str | None:
        return self._map.get(library_id)


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
def test_drift_decorator_missing_registered_library(tmp_path: Path, monkeypatch) -> None:
    """Source imports a registered haywire library but the decorator
    omits it — drift on the decorator side, not pyproject."""
    import importlib.metadata as _meta

    # Pin the installed version so the `~=0.0.1` floor below never lags it,
    # keeping this test about decorator drift only (not version lag) regardless
    # of the workspace's lockstep release version.
    monkeypatch.setattr(_meta, "version", lambda dist: "0.0.1")
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
def test_drift_no_drift_when_everything_declared(tmp_path: Path, monkeypatch) -> None:
    """All imports declared in both places — no drift."""
    import importlib.metadata as _meta

    # Pin installed versions so the `~=0.0.1` floors never lag them; this test
    # asserts "no drift", which must hold independent of the workspace's
    # current lockstep release version.
    monkeypatch.setattr(_meta, "version", lambda dist: "0.0.1")
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
def test_drift_extra_declarations_dont_count_as_drift(tmp_path: Path, monkeypatch) -> None:
    """Declared but unused deps must NOT be flagged: false positives would
    block users with optional or transitive deps."""
    import importlib.metadata as _meta

    monkeypatch.setattr(_meta, "version", lambda dist: "0.0.1")
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


@pytest.mark.unit
def test_drift_handles_invalid_os_declaration_gracefully(tmp_path: Path) -> None:
    """A valid TOML with an invalid [tool.haywire].os value should NOT crash
    detect_share_drift; it degrades the same way a malformed pyproject does,
    via read_manifest_lenient."""
    lib = _make_library(
        tmp_path,
        init_body_imports="from haywire.core.node.registry import NodeRegistry\n",
    )
    pyproject = lib / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + '\n[tool.haywire]\nos = ["freebsd"]\n')
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


# ──────────────────────────────────────────────────────────────────────────────
# pyproject_version_lag (spec §12) — declared haybale floors that lag installed
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_lag_flagged_for_haybale_dep_with_tilde_equals(tmp_path: Path, monkeypatch) -> None:
    """A haybale-* dep declared `~=` against a floor below the installed version
    should be flagged as version lag (spec §12.2)."""
    import importlib.metadata as _meta

    monkeypatch.setattr(_meta, "version", lambda dist: "0.5.0" if dist == "haybale-core" else "0.0.0")
    lib = _make_library(
        tmp_path,
        pyproject_deps=["haybale-core~=0.1.0"],
        init_body_imports="from haybale_core import types\n",
    )
    drift = detect_share_drift(lib)
    assert drift.pyproject_version_lag == [("haybale-core", "0.1.0", "0.5.0")]
    assert drift.has_drift


@pytest.mark.unit
def test_lag_flagged_for_haybale_dep_with_gte(tmp_path: Path, monkeypatch) -> None:
    """`>=` operator is also lag-eligible per spec §12.2."""
    import importlib.metadata as _meta

    monkeypatch.setattr(_meta, "version", lambda dist: "0.3.0" if dist == "haybale-core" else "0.0.0")
    lib = _make_library(
        tmp_path,
        pyproject_deps=["haybale-core>=0.1.0"],
        init_body_imports="from haybale_core import types\n",
    )
    drift = detect_share_drift(lib)
    assert drift.pyproject_version_lag == [("haybale-core", "0.1.0", "0.3.0")]


@pytest.mark.unit
def test_lag_not_flagged_for_exact_pin(tmp_path: Path, monkeypatch) -> None:
    """`==` is a deliberate pin; spec §12.2 says it must NOT be lag-flagged
    even if the installed version is higher."""
    import importlib.metadata as _meta

    monkeypatch.setattr(_meta, "version", lambda dist: "0.5.0" if dist == "haybale-core" else "0.0.0")
    lib = _make_library(
        tmp_path,
        pyproject_deps=["haybale-core==0.1.0"],
        init_body_imports="from haybale_core import types\n",
    )
    drift = detect_share_drift(lib)
    assert drift.pyproject_version_lag == []


@pytest.mark.unit
def test_lag_not_flagged_for_upper_bound(tmp_path: Path, monkeypatch) -> None:
    """`<` and `<=` are upper bounds, not floors; never flagged."""
    import importlib.metadata as _meta

    monkeypatch.setattr(_meta, "version", lambda dist: "0.5.0" if dist == "haybale-core" else "0.0.0")
    lib = _make_library(
        tmp_path,
        pyproject_deps=["haybale-core<2.0"],
        init_body_imports="from haybale_core import types\n",
    )
    drift = detect_share_drift(lib)
    assert drift.pyproject_version_lag == []


@pytest.mark.unit
def test_lag_not_flagged_for_third_party_dep(tmp_path: Path, monkeypatch) -> None:
    """Spec §12.1 critical correctness property: third-party deps (not
    registered as haywire libraries) must NEVER be lag-checked. Acting on
    third-party lag would gratuitously narrow library compatibility based
    on the author's dev-machine state."""
    import importlib.metadata as _meta

    # Pretend numpy is installed at 2.0 but library declares numpy>=1.0.
    monkeypatch.setattr(_meta, "version", lambda dist: "2.0.0" if dist == "numpy" else "0.0.0")
    lib = _make_library(
        tmp_path,
        pyproject_deps=["numpy>=1.0"],
        init_body_imports="",  # no imports → no missing-deps complaint either
    )
    drift = detect_share_drift(lib)
    assert drift.pyproject_version_lag == []
    # numpy is not registered as a haywire library, so even though the floor
    # genuinely lags, the gate stays silent.


@pytest.mark.unit
def test_lag_not_flagged_when_installed_equals_floor(tmp_path: Path, monkeypatch) -> None:
    """`installed == declared_floor` is not lag — only strictly greater."""
    import importlib.metadata as _meta

    monkeypatch.setattr(_meta, "version", lambda dist: "0.1.0" if dist == "haybale-core" else "0.0.0")
    lib = _make_library(
        tmp_path,
        pyproject_deps=["haybale-core~=0.1.0"],
        init_body_imports="from haybale_core import types\n",
    )
    drift = detect_share_drift(lib)
    assert drift.pyproject_version_lag == []


@pytest.mark.unit
def test_lag_skipped_when_dep_not_installed(tmp_path: Path, monkeypatch) -> None:
    """If a declared dep isn't installed, can't compute lag — skip silently."""
    import importlib.metadata as _meta

    def _raise(dist):
        raise _meta.PackageNotFoundError(dist)

    monkeypatch.setattr(_meta, "version", _raise)
    lib = _make_library(
        tmp_path,
        pyproject_deps=["haybale-core~=0.1.0"],
        init_body_imports="from haybale_core import types\n",
    )
    drift = detect_share_drift(lib)
    assert drift.pyproject_version_lag == []


@pytest.mark.unit
def test_drift_report_includes_lag_section(tmp_path: Path, monkeypatch) -> None:
    """The human report must mention lag explicitly so users understand
    why share is warning/failing."""
    import importlib.metadata as _meta

    monkeypatch.setattr(_meta, "version", lambda dist: "0.5.0" if dist == "haybale-core" else "0.0.0")
    lib = _make_library(
        tmp_path,
        pyproject_deps=["haybale-core~=0.1.0"],
        init_body_imports="from haybale_core import types\n",
    )
    drift = detect_share_drift(lib)
    report = _format_drift_report(drift)
    assert "haybale-core" in report
    assert "0.1.0" in report
    assert "0.5.0" in report
    assert "lagging" in report.lower()
