"""Step 2 — dependency drift detection and the Union/Replace decision."""

from pathlib import Path
from unittest.mock import patch

import pytest
import toml

from haywire_studio.share import DepDrift
from haywire_studio.share_pipeline.pipeline import SharePipeline

pytestmark = pytest.mark.unit


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Two barn libraries with declared deps, no git needed for this step."""
    repo = tmp_path / "project"
    for name, deps in (("haybale-alpha", '["haywire-core~=0.0.1"]'), ("haybale-beta", "[]")):
        lib = repo / "barn" / name
        module = lib / name.replace("-", "_")
        module.mkdir(parents=True)
        (lib / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "0.1.0"\ndependencies = {deps}\n'
        )
        (module / "__init__.py").write_text(
            '@library(label="X", id="x", dependencies=["haybale_core"])\nclass Library: pass\n'
        )
    return repo


def test_check_drift_runs_every_barn_library(project: Path) -> None:
    seen: list[Path] = []

    def _fake(lib_dir: Path) -> DepDrift:
        seen.append(lib_dir)
        return DepDrift(lib_dir=lib_dir)

    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_fake):
        SharePipeline(project).check_drift()

    assert sorted(p.name for p in seen) == ["haybale-alpha", "haybale-beta"]


def test_clean_project_needs_no_decision(project: Path) -> None:
    with patch(
        "haywire_studio.share_pipeline.pipeline.detect_share_drift",
        side_effect=lambda lib_dir: DepDrift(lib_dir=lib_dir),
    ):
        report = SharePipeline(project).check_drift()

    assert report.needs_decision is False
    assert report.drifted == []
    assert report.unresolved_only == []


def test_actionable_drift_needs_a_decision(project: Path) -> None:
    def _drifty(lib_dir: Path) -> DepDrift:
        if lib_dir.name == "haybale-alpha":
            return DepDrift(lib_dir=lib_dir, pyproject_missing=["numpy"])
        return DepDrift(lib_dir=lib_dir)

    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_drifty):
        report = SharePipeline(project).check_drift()

    assert report.needs_decision is True
    assert [d.lib_dir.name for d in report.drifted] == ["haybale-alpha"]


def test_unresolved_imports_alone_never_gate(project: Path) -> None:
    """Unresolved imports are usually dynamic — gating on them would fire every run."""

    def _unresolved(lib_dir: Path) -> DepDrift:
        return DepDrift(lib_dir=lib_dir, unresolved=["some.dynamic.module"])

    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_unresolved):
        report = SharePipeline(project).check_drift()

    assert report.needs_decision is False
    assert len(report.unresolved_only) == 2


def test_apply_drift_union_is_additive(project: Path) -> None:
    """Union keeps existing declarations and adds the detected ones."""
    lib = project / "barn" / "haybale-alpha"
    drift = DepDrift(lib_dir=lib, pyproject_missing=["numpy"])
    report = type("R", (), {"drifted": [drift], "unresolved_only": []})()

    def _fake_fix(d: DepDrift) -> None:
        data = toml.loads((d.lib_dir / "pyproject.toml").read_text())
        deps = sorted({*data["project"]["dependencies"], "numpy>=1.0"})
        data["project"]["dependencies"] = deps
        (d.lib_dir / "pyproject.toml").write_text(toml.dumps(data))

    pipeline = SharePipeline(project)
    with patch("haywire_studio.share_pipeline.pipeline.apply_drift_fix", side_effect=_fake_fix):
        written = pipeline.apply_drift_union(report)  # type: ignore[arg-type]

    deps = toml.loads((lib / "pyproject.toml").read_text())["project"]["dependencies"]
    assert "numpy>=1.0" in deps
    assert "haywire-core~=0.0.1" in deps  # nothing removed
    assert lib / "pyproject.toml" in written
    assert lib / "pyproject.toml" in pipeline.written


def test_apply_drift_union_translates_manifest_read_error(project: Path) -> None:
    """A malformed pyproject.toml surfaces as ManifestError, not the raw ManifestReadError."""
    from haywire_studio.share_pipeline import ManifestError

    lib = project / "barn" / "haybale-alpha"
    (lib / "pyproject.toml").write_text("this is not [[[ valid toml")
    drift = DepDrift(lib_dir=lib, pyproject_missing=["numpy"])
    report = type("R", (), {"drifted": [drift], "unresolved_only": []})()

    with pytest.raises(ManifestError):
        SharePipeline(project).apply_drift_union(report)  # type: ignore[arg-type]


def test_apply_drift_replace_can_remove_declarations(project: Path) -> None:
    """Replace overwrites with exactly what was detected — that's why it's a decision."""
    lib = project / "barn" / "haybale-alpha"
    drift = DepDrift(lib_dir=lib, pyproject_missing=["numpy"])
    report = type("R", (), {"drifted": [drift], "unresolved_only": []})()

    class _Detected:
        pyproject = ["numpy>=1.0"]
        library_decorator = ["haybale_core"]
        unresolved: list[str] = []

    pipeline = SharePipeline(project)
    with patch(
        "haywire_studio.share_pipeline.pipeline.detect_deps",
        return_value=_Detected(),
    ):
        written = pipeline.apply_drift_replace(report)  # type: ignore[arg-type]

    deps = toml.loads((lib / "pyproject.toml").read_text())["project"]["dependencies"]
    assert deps == ["numpy>=1.0"]
    assert "haywire-core~=0.0.1" not in deps  # removed — the destructive path
    assert lib / "pyproject.toml" in written


def test_apply_drift_replace_rewrites_the_decorator(project: Path) -> None:
    lib = project / "barn" / "haybale-alpha"
    init_file = lib / "haybale_alpha" / "__init__.py"
    drift = DepDrift(lib_dir=lib, decorator_missing=["haybale_studio"])
    report = type("R", (), {"drifted": [drift], "unresolved_only": []})()

    class _Detected:
        pyproject: list[str] = []
        library_decorator = ["haybale_studio"]
        unresolved: list[str] = []

    with patch("haywire_studio.share_pipeline.pipeline.detect_deps", return_value=_Detected()):
        written = SharePipeline(project).apply_drift_replace(report)  # type: ignore[arg-type]

    content = init_file.read_text()
    assert "haybale-studio" in content or "haybale_studio" in content
    assert init_file in written


def test_apply_drift_replace_translates_manifest_read_error(project: Path) -> None:
    """A malformed pyproject.toml surfaces as ManifestError, not the raw TomlDecodeError."""
    from haywire_studio.share_pipeline import ManifestError

    lib = project / "barn" / "haybale-alpha"
    (lib / "pyproject.toml").write_text("this is not [[[ valid toml")
    drift = DepDrift(lib_dir=lib, pyproject_missing=["numpy"])
    report = type("R", (), {"drifted": [drift], "unresolved_only": []})()

    class _Detected:
        pyproject = ["numpy>=1.0"]
        library_decorator = ["haybale_core"]
        unresolved: list[str] = []

    with patch(
        "haywire_studio.share_pipeline.pipeline.detect_deps",
        return_value=_Detected(),
    ):
        with pytest.raises(ManifestError):
            SharePipeline(project).apply_drift_replace(report)  # type: ignore[arg-type]


def test_acknowledge_drift_records_the_choice(project: Path) -> None:
    pipeline = SharePipeline(project)
    assert pipeline.drift_acknowledged is False
    pipeline.acknowledge_drift()
    assert pipeline.drift_acknowledged is True


def test_written_set_never_duplicates(project: Path) -> None:
    lib = project / "barn" / "haybale-alpha"
    drift = DepDrift(lib_dir=lib, pyproject_missing=["numpy"])
    report = type("R", (), {"drifted": [drift], "unresolved_only": []})()
    pipeline = SharePipeline(project)
    with patch("haywire_studio.share_pipeline.pipeline.apply_drift_fix"):
        pipeline.apply_drift_union(report)  # type: ignore[arg-type]
        pipeline.apply_drift_union(report)  # type: ignore[arg-type]
    assert len(pipeline.written) == len(set(pipeline.written))
