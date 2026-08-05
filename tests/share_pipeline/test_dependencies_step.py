"""Detect (pure) and the dependency writes that follow it.

The invariant these exist to protect: each write touches only the entries it
owns. The framework floor used to be rewritten as a side effect of resolving
unrelated drift, and the ordering that hid it was accidental.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
import toml

from haywire.core.publishing import DepDrift
from haywire.core.publishing.pipeline.pipeline import SharePipeline
from haywire.core.publishing.pipeline.steps import detect as steps_detect

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

    SharePipeline(project).apply_additions({lib: ["haywire-core>=9.9.9", "numpy>=2.0"]})

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
    pipeline.apply_additions({lib: ["numpy>=2.0"]})

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
    pipeline.apply_additions({})
    pipeline.apply_floors({})

    assert (lib / "pyproject.toml").read_text() == before
    assert pipeline.written == []


def test_decorator_gap_alone_is_not_drift(project: Path) -> None:
    """It is repaired unconditionally, so it can never be a state to resolve.

    Refusing to publish over something the tool always fixes would be asking a
    question with one answer.
    """
    with patch.object(
        steps_detect,
        "detect_share_drift",
        side_effect=lambda lib_dir: DepDrift(lib_dir=lib_dir, decorator_missing=["haybale_studio"]),
    ):
        report = SharePipeline(project).check_drift()

    assert report.needs_decision is False
    # Still reported — the author is told, just not asked.
    assert len(report.findings_only) == 2


def test_decorator_registrations_are_applied_in_union_mode(project: Path) -> None:
    """Existing entries survive: a name added by hand for a dynamic import
    would otherwise be dropped by a tool that cannot see that import.

    Note ``merge_decorator_list_field`` normalizes separators, so the kept
    entry may come back hyphenated — the registration is what must survive,
    not its spelling.
    """
    lib = project / "barn" / "haybale-alpha"
    init = lib / "haybale_alpha" / "__init__.py"

    pipeline = SharePipeline(project)
    pipeline.apply_decorator_registrations({lib: ["haybale_studio"]})

    source = init.read_text()
    assert "haybale_studio" in source
    assert "haybale_core" in source or "haybale-core" in source
    assert init in pipeline.written


def test_decorator_registrations_never_touch_pyproject(project: Path) -> None:
    """Separate carriers, separate writes — this one only edits __init__.py."""
    lib = project / "barn" / "haybale-alpha"
    before = (lib / "pyproject.toml").read_text()

    pipeline = SharePipeline(project)
    pipeline.apply_decorator_registrations({lib: ["haybale_studio"]})

    assert (lib / "pyproject.toml").read_text() == before
    assert [p.name for p in pipeline.written] == ["__init__.py"]


def test_acknowledge_undeclared_records_the_choice(project: Path) -> None:
    pipeline = SharePipeline(project)
    assert pipeline.undeclared_acknowledged is False

    pipeline.acknowledge_undeclared()

    assert pipeline.undeclared_acknowledged is True


def test_written_set_never_duplicates(project: Path) -> None:
    lib = project / "barn" / "haybale-alpha"
    pipeline = SharePipeline(project)

    pipeline.apply_framework(">=0.0.38")
    pipeline.apply_additions({lib: ["numpy>=2.0"]})

    assert pipeline.written.count(lib / "pyproject.toml") == 1


# ── formatting ───────────────────────────────────────────────────────────────


def test_writes_preserve_layout_and_entry_comments(project: Path) -> None:
    """A one-entry-per-line array stays that way, comments and all.

    tomlkit keeps an array's existing layout across in-place `append`,
    `__setitem__` and `del`, but assigning a fresh Python list replaces the
    array wholesale — collapsing it to one long inline row and silently
    deleting every per-entry comment the author wrote. `dep_edit` therefore
    mutates the live array and never reassigns it.
    """
    lib = project / "barn" / "haybale-alpha"
    (lib / "pyproject.toml").write_text(
        "[project]\n"
        'name = "haybale-alpha"\n'
        'version = "0.1.0"\n'
        "# what this library needs\n"
        "dependencies = [\n"
        '    "haywire-core>=0.0.31",\n'
        '    "toml",  # loose on purpose\n'
        '    "nicegui>=3.12.1",\n'
        "]\n"
    )

    pipeline = SharePipeline(project)
    pipeline.apply_framework(">=0.0.38")
    pipeline.apply_additions({lib: ["numpy>=2.0"]})
    pipeline.apply_removals({lib: ["nicegui"]})

    text = (lib / "pyproject.toml").read_text()
    assert '    "haywire-core>=0.0.38",\n' in text
    assert '    "numpy>=2.0",\n' in text
    assert '    "toml",  # loose on purpose\n' in text
    assert "# what this library needs\n" in text
    assert "nicegui" not in text


def test_an_inline_array_is_left_inline(project: Path) -> None:
    """Style is preserved, not imposed — this is the author's file."""
    lib = project / "barn" / "haybale-alpha"
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.1.0"\ndependencies = ["toml"]\n'
    )

    SharePipeline(project).apply_additions({lib: ["numpy>=2.0"]})

    assert 'dependencies = ["toml", "numpy>=2.0"]' in (lib / "pyproject.toml").read_text()


# ── apply_all: collect-then-apply-once ───────────────────────────────────────


def test_apply_all_with_an_untouched_decision_set_writes_nothing(project: Path) -> None:
    """The default ShareDecisions must be a provable no-op.

    This is what makes deferring the writes safe: a flow abandoned before the
    author confirms leaves the tree exactly as it found it, so there is
    nothing to roll back.
    """
    from haywire.core.publishing.pipeline import ShareDecisions

    pipeline = SharePipeline(project)
    before = {lib: (lib / "pyproject.toml").read_text() for lib in pipeline._barn_library_dirs()}

    written = pipeline.apply_all(ShareDecisions())

    assert written == []
    assert pipeline.written == []
    for lib, text in before.items():
        assert (lib / "pyproject.toml").read_text() == text


def test_apply_all_writes_the_framework_floor_before_the_other_entries(project: Path) -> None:
    """Order is load-bearing, not cosmetic.

    plan_framework() reads the author's ACTUAL prior declaration. When the
    framework write ran after the other dependency writes, "keep the current
    declaration" computed from a value another step had already rewritten and
    the recommended option silently raised the floor. apply_all must preserve
    the order the incremental path established.
    """
    from haywire.core.publishing.pipeline import ShareDecisions

    pipeline = SharePipeline(project)
    calls: list[str] = []

    def _record(name):
        def _inner(*_args, **_kwargs):
            calls.append(name)
            return []

        return _inner

    with (
        patch.object(SharePipeline, "apply_framework", _record("framework")),
        patch.object(SharePipeline, "apply_decorator_registrations", _record("registrations")),
        patch.object(SharePipeline, "apply_removals", _record("removals")),
        patch.object(SharePipeline, "apply_additions", _record("additions")),
        patch.object(SharePipeline, "apply_floors", _record("floors")),
    ):
        pipeline.apply_all(
            ShareDecisions(
                framework=">=0.0.31",
                registrations={Path("a"): ["x"]},
                removals={Path("a"): ["y"]},
                additions={Path("a"): ["z"]},
                floors={Path("a"): ["w>=1"]},
            )
        )

    assert calls == ["framework", "registrations", "removals", "additions", "floors"]


def test_apply_all_applies_the_real_writes_and_accumulates_them(project: Path) -> None:
    """End to end over the real appliers: the write set is what step 5 stages."""
    from haywire.core.publishing.pipeline import ShareDecisions

    pipeline = SharePipeline(project)
    alpha = project / "barn" / "haybale-alpha"

    written = pipeline.apply_all(ShareDecisions(framework=">=0.0.31", additions={alpha: ["numpy>=1.0"]}))

    assert alpha / "pyproject.toml" in written
    assert "numpy>=1.0" in _deps(alpha)
    assert any(d.startswith("haywire-core>=0.0.31") for d in _deps(alpha))
    # Recorded once, not twice, even though two appliers touched the same file.
    assert pipeline.written.count(alpha / "pyproject.toml") == 1


def test_apply_all_records_the_undeclared_acknowledgement(project: Path) -> None:
    """The one flag that has no file to write, so it would be easy to drop."""
    from haywire.core.publishing.pipeline import ShareDecisions

    pipeline = SharePipeline(project)
    assert pipeline.undeclared_acknowledged is False

    pipeline.apply_all(ShareDecisions(undeclared_acknowledged=True))

    assert pipeline.undeclared_acknowledged is True
