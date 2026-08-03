"""The framework-requirement step: option generation, validation, dual write.

A floor is a restriction on CONSUMERS, not a record of what the author
tested. Raising it forces every consumer to upgrade their project first, so
the recommended option is always the lowest necessary one — keep what is
already declared.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from typing import cast

import pytest
import toml

from haywire_studio.packaging.share.pipeline import SharePipeline


def _apply_recorder(applied: list, spec) -> list:
    """Record *spec* and return an empty result list.

    A helper rather than ``applied.append(spec) or []`` because
    ``list.append`` returns None, which mypy rejects in value position.
    """
    applied.append(spec)
    return []


pytestmark = pytest.mark.unit


def _project(tmp_path: Path, *, floor: str = ">=0.0.31") -> Path:
    lib = tmp_path / "barn" / "haybale-alpha"
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        textwrap.dedent(f"""
            [project]
            name = "haybale-alpha"
            version = "0.1.0"
            dependencies = ["haywire-core{floor}", "numpy>=1.0"]
        """).lstrip()
    )
    return tmp_path


def test_plan_offers_keep_raise_and_compatible(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "haywire_studio.packaging.share.pipeline.steps.framework._installed_core_version",
        lambda: "0.0.34",
    )
    plan = SharePipeline(_project(tmp_path)).plan_framework()

    assert plan.installed == "0.0.34"
    assert plan.declared == ">=0.0.31"
    assert [o.specifier for o in plan.options] == [">=0.0.31", ">=0.0.34", "~=0.0.31"]


def test_keeping_the_declared_floor_is_the_recommended_option(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "haywire_studio.packaging.share.pipeline.steps.framework._installed_core_version",
        lambda: "0.0.34",
    )
    plan = SharePipeline(_project(tmp_path)).plan_framework()

    recommended = [o for o in plan.options if o.recommended]
    assert len(recommended) == 1
    assert recommended[0].specifier == ">=0.0.31"


def test_raise_option_counts_the_consumers_it_locks_out(tmp_path, monkeypatch):
    """Consequence-annotated, following the deps-drift precedent: the option
    that excludes consumers must say so concretely."""
    monkeypatch.setattr(
        "haywire_studio.packaging.share.pipeline.steps.framework._installed_core_version",
        lambda: "0.0.34",
    )
    plan = SharePipeline(_project(tmp_path)).plan_framework()

    raise_option = next(o for o in plan.options if o.specifier == ">=0.0.34")
    assert "0.0.31" in raise_option.consequence
    assert "0.0.33" in raise_option.consequence


def test_no_ceiling_in_any_default_option(tmp_path, monkeypatch):
    """A <0.1.0 stamped today becomes a lie the moment 0.1.0 ships. Authors who
    want a ceiling type one; ~= is offered but never recommended."""
    monkeypatch.setattr(
        "haywire_studio.packaging.share.pipeline.steps.framework._installed_core_version",
        lambda: "0.0.34",
    )
    plan = SharePipeline(_project(tmp_path)).plan_framework()

    recommended = next(o for o in plan.options if o.recommended)
    assert "<" not in recommended.specifier


def test_apply_writes_the_floor_into_every_barn_library(tmp_path):
    root = _project(tmp_path)
    second = root / "barn" / "haybale-beta"
    second.mkdir()
    (second / "pyproject.toml").write_text(
        '[project]\nname = "haybale-beta"\nversion = "0.1.0"\ndependencies = ["haywire-core>=0.0.31"]\n'
    )
    pipeline = SharePipeline(root)

    written = pipeline.apply_framework(">=0.0.34")

    assert len(written) == 2
    for lib in ("haybale-alpha", "haybale-beta"):
        deps = toml.loads((root / "barn" / lib / "pyproject.toml").read_text())["project"]["dependencies"]
        assert "haywire-core>=0.0.34" in deps
        assert "numpy>=1.0" in deps or lib == "haybale-beta"
    assert pipeline.requires_haywire == ">=0.0.34"


def test_apply_adds_the_dependency_when_undeclared(tmp_path):
    root = tmp_path
    lib = root / "barn" / "haybale-alpha"
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.1.0"\ndependencies = ["numpy>=1.0"]\n'
    )

    SharePipeline(root).apply_framework(">=0.0.34")

    deps = toml.loads((lib / "pyproject.toml").read_text())["project"]["dependencies"]
    assert "haywire-core>=0.0.34" in deps


def test_apply_rejects_an_invalid_specifier(tmp_path):
    from haywire_studio.packaging.share.pipeline import InvalidSpecifierError

    with pytest.raises(InvalidSpecifierError):
        SharePipeline(_project(tmp_path)).apply_framework("not a specifier")


def test_apply_rejects_a_bare_version(tmp_path):
    """requires_haywire is a specifier, never a bare version — "0.0.34" alone
    is not a valid SpecifierSet."""
    from haywire_studio.packaging.share.pipeline import InvalidSpecifierError

    with pytest.raises(InvalidSpecifierError):
        SharePipeline(_project(tmp_path)).apply_framework("0.0.34")


def test_reordered_equivalent_specifiers_are_not_drift(tmp_path):
    """packaging reorders on str(): ">=0.0.31,<1.0.0" round-trips as
    "<1.0.0,>=0.0.31". Comparing raw strings would report false drift."""
    from haywire_studio.packaging.share.pipeline.steps.framework import specifiers_equal

    assert specifiers_equal(">=0.0.31,<1.0.0", "<1.0.0,>=0.0.31")
    assert not specifiers_equal(">=0.0.31", ">=0.0.34")


def test_marketstall_entry_carries_the_same_answer_as_the_pyproject_floor(tmp_path, monkeypatch):
    """One authored answer, two disjoint carriers: the wheel's Requires-Dist
    floor guards `uv add`, requires_haywire guards the marketplace install."""
    from haywire_studio.packaging.share.marketstall import _build_entry_for_library

    root = _project(tmp_path)
    pipeline = SharePipeline(root)
    pipeline.apply_framework(">=0.0.34")

    entry = cast(
        dict,
        _build_entry_for_library(
            root / "barn" / "haybale-alpha", requires_haywire=cast(str, pipeline.requires_haywire)
        ),
    )

    assert entry["requires_haywire"] == ">=0.0.34"
    deps = toml.loads((root / "barn" / "haybale-alpha" / "pyproject.toml").read_text())["project"][
        "dependencies"
    ]
    assert "haywire-core>=0.0.34" in deps


def test_entry_omits_requires_haywire_when_undeclared(tmp_path):
    """A standalone write_marketstall() outside the pipeline declares nothing;
    the key is simply absent rather than an empty string."""
    from haywire_studio.packaging.share.marketstall import _build_entry_for_library

    root = _project(tmp_path)
    entry = _build_entry_for_library(root / "barn" / "haybale-alpha")

    assert "requires_haywire" not in cast(dict, entry)


def test_yes_without_the_flag_keeps_the_declared_floor(tmp_path, monkeypatch):
    """--yes with no --requires-haywire changes nothing and locks nobody out.
    Unlike the drift precedent (where BOTH options mutate and one is lossy),
    doing nothing here is safe, so a refusal would be pointless friction."""
    from haywire_studio.packaging.share import cli as share_cli

    applied: list[str] = []
    monkeypatch.setattr(SharePipeline, "apply_framework", lambda self, spec: _apply_recorder(applied, spec))

    assert share_cli._resolve_framework_answer(SharePipeline(_project(tmp_path)), None) is None
    assert applied == []


def test_yes_with_the_flag_raises_the_floor(tmp_path, monkeypatch):
    """Raising a floor — the consumer-excluding direction — always requires the
    explicit flag."""
    from haywire_studio.packaging.share import cli as share_cli

    applied: list[str] = []
    monkeypatch.setattr(SharePipeline, "apply_framework", lambda self, spec: _apply_recorder(applied, spec))

    pipeline = SharePipeline(_project(tmp_path))
    assert share_cli._resolve_framework_answer(pipeline, ">=0.0.34") == ">=0.0.34"
    assert applied == [">=0.0.34"]
