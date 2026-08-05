# tests/test_deps_cli.py
"""``haywire deps check`` — decoupled from SharePipeline, gates on actionable drift only.

Every test patches ``haywire_studio.packaging.deps.detect_share_drift`` directly rather
than scaffolding real importable library sources: this command's own logic (barn
scan, print formatting, exit-code gating) is what's under test, not
``detect_share_drift`` itself (covered by tests/test_share_drift.py).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from haywire_studio.packaging import deps as deps_cli
from haywire_studio.packaging.deps import EXIT_DRIFT, EXIT_OK, run_deps_check_cli
from haywire.core.publishing import DepDrift

pytestmark = pytest.mark.unit


def _make_barn_library(repo_root: Path, name: str = "haybale-alpha") -> Path:
    """A barn/<name> directory with just a pyproject.toml — enough to be scanned."""
    lib_dir = repo_root / "barn" / name
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.1.0"\n')
    return lib_dir


@pytest.mark.unit
def test_no_drift_exits_ok_and_prints_confirmation(tmp_path: Path, capsys) -> None:
    lib_dir = _make_barn_library(tmp_path)

    with patch.object(deps_cli, "detect_share_drift", side_effect=lambda d: DepDrift(lib_dir=d)):
        exit_code = run_deps_check_cli(tmp_path)

    assert exit_code == EXIT_OK
    out = capsys.readouterr().out
    assert "No dependency drift" in out
    assert lib_dir.name not in out


@pytest.mark.unit
def test_actionable_drift_exits_drift_and_prints_each_kind(tmp_path: Path, capsys) -> None:
    lib_dir = _make_barn_library(tmp_path)
    drift = DepDrift(
        lib_dir=lib_dir,
        pyproject_missing=["haywire-core"],
        decorator_missing=["haybale_core"],
        pyproject_version_lag=[("haybale-core", "0.1.0", "0.2.0")],
    )

    with patch.object(deps_cli, "detect_share_drift", side_effect=lambda d: drift):
        exit_code = run_deps_check_cli(tmp_path)

    out = capsys.readouterr().out
    assert exit_code == EXIT_DRIFT
    assert lib_dir.name in out
    assert "+ pyproject.toml: haywire-core" in out
    assert "+ @library(dependencies): haybale_core" in out
    assert "~ haybale-core: declared 0.1.0, installed 0.2.0" in out
    assert "Dependency drift found" in out


@pytest.mark.unit
def test_unresolved_only_is_informational_and_exits_ok(tmp_path: Path, capsys) -> None:
    """The one test that pins Q3's decision: unresolved imports are printed
    but never gate the exit code — they're advisory, not actionable drift."""
    lib_dir = _make_barn_library(tmp_path)
    drift = DepDrift(lib_dir=lib_dir, unresolved=["some.weird.import"])

    with patch.object(deps_cli, "detect_share_drift", side_effect=lambda d: drift):
        exit_code = run_deps_check_cli(tmp_path)

    out = capsys.readouterr().out
    assert exit_code == EXIT_OK
    assert "unresolved imports" in out
    assert "some.weird.import" in out
    assert "No dependency drift" in out


@pytest.mark.unit
def test_no_barn_directory_is_not_a_failure(tmp_path: Path, capsys) -> None:
    exit_code = run_deps_check_cli(tmp_path)

    out = capsys.readouterr().out
    assert exit_code == EXIT_OK
    assert "Nothing to check" in out


@pytest.mark.unit
def test_never_imports_or_constructs_share_pipeline() -> None:
    """Global constraint: `deps check` must stay decoupled from SharePipeline.

    Checks import statements specifically (not a raw substring scan of the
    source) since the module's own docstring names ``SharePipeline`` in
    prose to document this very constraint.
    """
    import ast

    import haywire_studio.packaging.deps as deps_cli_module

    assert "SharePipeline" not in dir(deps_cli_module)
    src = deps_cli_module.__spec__.loader.get_source(deps_cli_module.__name__)  # type: ignore[union-attr]
    imported_modules = set()
    imported_names: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
    assert "haywire.core.publishing.pipeline" not in imported_modules
    assert "SharePipeline" not in imported_names
