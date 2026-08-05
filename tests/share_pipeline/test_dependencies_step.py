"""Detect (pure) and the dependency writes that follow it.

The invariant these exist to protect: each write touches only the entries it
owns. The framework floor used to be rewritten as a side effect of resolving
unrelated drift, and the ordering that hid it was accidental.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
import toml

from haywire_studio.packaging.share import DepDrift
from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline
from haywire_studio.packaging.share.pipeline.steps import detect as steps_detect

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


def _deps(lib_dir: Path) -> list[str]:
    return toml.loads((lib_dir / "pyproject.toml").read_text())["project"]["dependencies"]


def _write_deps(lib_dir: Path, deps: list[str]) -> None:
    name = lib_dir.name
    body = toml.dumps({"project": {"name": name, "version": "0.1.0", "dependencies": deps}})
    (lib_dir / "pyproject.toml").write_text(body)


# ── detect ───────────────────────────────────────────────────────────────────


def test_check_drift_runs_every_barn_library(project: Path) -> None:
    seen: list[Path] = []

    def _fake(lib_dir: Path) -> DepDrift:
        seen.append(lib_dir)
        return DepDrift(lib_dir=lib_dir)

    with patch.object(steps_detect, "detect_share_drift", side_effect=_fake):
        SharePipeline(project).check_drift()

    assert sorted(p.name for p in seen) == ["haybale-alpha", "haybale-beta"]


def test_clean_project_needs_no_decision(project: Path) -> None:
    with patch.object(
        steps_detect, "detect_share_drift", side_effect=lambda lib_dir: DepDrift(lib_dir=lib_dir)
    ):
        report = SharePipeline(project).check_drift()

    assert report.needs_decision is False
    assert report.drifted == []
    assert report.findings_only == []


def test_undeclared_import_needs_a_decision(project: Path) -> None:
    def _drifty(lib_dir: Path) -> DepDrift:
        if lib_dir.name == "haybale-alpha":
            return DepDrift(lib_dir=lib_dir, pyproject_missing=["numpy"])
        return DepDrift(lib_dir=lib_dir)

    with patch.object(steps_detect, "detect_share_drift", side_effect=_drifty):
        report = SharePipeline(project).check_drift()

    assert report.needs_decision is True
    assert [d.lib_dir.name for d in report.drifted] == ["haybale-alpha"]


@pytest.mark.parametrize(
    ("kwargs", "why"),
    [
        ({"unresolved": ["some.dynamic.module"]}, "unresolved imports are usually dynamic"),
        ({"unused_declarations": ["numpy"]}, "an unused declaration is inert for consumers"),
        (
            {"pyproject_version_lag": [("haybale-core", "0.0.1", "0.5.0")]},
            "a floor below installed is an observation, not a defect",
        ),
    ],
)
def test_non_breaking_findings_never_gate(project: Path, kwargs: dict, why: str) -> None:
    """Only an undeclared import breaks a consumer's install.

    Everything else is reported so the author can act on it, and gating on any
    of them would fire on nearly every run.
    """
    with patch.object(
        steps_detect,
        "detect_share_drift",
        side_effect=lambda lib_dir: DepDrift(lib_dir=lib_dir, **kwargs),
    ):
        report = SharePipeline(project).check_drift()

    assert report.needs_decision is False, why
    assert len(report.findings_only) == 2


# ── ownership ────────────────────────────────────────────────────────────────


def test_framework_write_touches_only_the_core_entry(project: Path) -> None:
    lib = project / "barn" / "haybale-alpha"
    _write_deps(lib, ["numpy>=1.0", "haywire-core~=0.0.1", "visiongraph[onnx,openvino]"])

    SharePipeline(project).apply_framework(">=0.0.38")

    assert _deps(lib) == ["numpy>=1.0", "haywire-core>=0.0.38", "visiongraph[onnx,openvino]"]


def test_additions_never_restate_an_existing_floor(project: Path) -> None:
    """An addition declares what is missing; changing a specifier is another step's job."""
    lib = project / "barn" / "haybale-alpha"

    SharePipeline(project).apply_additions({lib: ["haywire-core>=9.9.9", "numpy>=2.0"]}, {})

    assert _deps(lib) == ["haywire-core~=0.0.1", "numpy>=2.0"]


def test_removals_drop_only_the_named_dists(project: Path) -> None:
    lib = project / "barn" / "haybale-alpha"
    _write_deps(lib, ["numpy>=1.0", "haywire-core~=0.0.1", "toml"])

    SharePipeline(project).apply_removals({lib: ["numpy"]})

    assert _deps(lib) == ["haywire-core~=0.0.1", "toml"]


def test_extras_and_markers_survive_every_write(project: Path) -> None:
    """The lossy-round-trip bug: regenerating entries from detection drops
    extras, markers and direct references. Entry-level edits never read them."""
    lib = project / "barn" / "haybale-alpha"
    _write_deps(
        lib,
        [
            "visiongraph[onnx,openvino,mediapipe]",
            'depthai~=2.30; sys_platform == "darwin"',
            "haywire-core~=0.0.1",
        ],
    )

    pipeline = SharePipeline(project)
    pipeline.apply_framework(">=0.0.38")
    pipeline.apply_additions({lib: ["numpy>=2.0"]}, {})

    after = _deps(lib)
    assert "visiongraph[onnx,openvino,mediapipe]" in after
    assert 'depthai~=2.30; sys_platform == "darwin"' in after
    assert "haywire-core>=0.0.38" in after
    assert "numpy>=2.0" in after


def test_floors_rewrite_only_what_was_passed(project: Path) -> None:
    lib = project / "barn" / "haybale-alpha"
    _write_deps(lib, ["haybale-core>=0.0.32", "numpy>=1.0"])

    SharePipeline(project).apply_floors({lib: ["haybale-core>=0.0.38"]})

    assert _deps(lib) == ["haybale-core>=0.0.38", "numpy>=1.0"]


def test_empty_mappings_write_nothing(project: Path) -> None:
    """Keeping things as they are is a valid answer on every screen."""
    lib = project / "barn" / "haybale-alpha"
    before = (lib / "pyproject.toml").read_text()

    pipeline = SharePipeline(project)
    pipeline.apply_removals({})
    pipeline.apply_additions({}, {})
    pipeline.apply_floors({})

    assert (lib / "pyproject.toml").read_text() == before
    assert pipeline.written == []


def test_acknowledge_undeclared_records_the_choice(project: Path) -> None:
    pipeline = SharePipeline(project)
    assert pipeline.undeclared_acknowledged is False

    pipeline.acknowledge_undeclared()

    assert pipeline.undeclared_acknowledged is True


def test_written_set_never_duplicates(project: Path) -> None:
    lib = project / "barn" / "haybale-alpha"
    pipeline = SharePipeline(project)

    pipeline.apply_framework(">=0.0.38")
    pipeline.apply_additions({lib: ["numpy>=2.0"]}, {})

    assert pipeline.written.count(lib / "pyproject.toml") == 1
