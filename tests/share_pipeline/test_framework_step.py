"""The framework-requirement step: option generation, validation, dual write.

A floor is a restriction on CONSUMERS, not a record of what the author
tested. Raising it forces every consumer to upgrade their project first, so
the recommended option is always the lowest necessary one — keep what is
already declared.
"""

from __future__ import annotations

import textwrap
from types import SimpleNamespace
from pathlib import Path

from typing import cast

import pytest
import toml

from haywire.core.publishing.pipeline import SharePipeline


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
        "haywire.core.publishing.pipeline.steps.framework._installed_core_version",
        lambda: "0.0.34",
    )
    plan = SharePipeline(_project(tmp_path)).plan_framework()

    assert plan.installed == "0.0.34"
    assert plan.declared == ">=0.0.31"
    assert [o.specifier for o in plan.options] == [">=0.0.31", ">=0.0.34", "~=0.0.31"]


def test_keeping_the_declared_floor_is_the_recommended_option(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "haywire.core.publishing.pipeline.steps.framework._installed_core_version",
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
        "haywire.core.publishing.pipeline.steps.framework._installed_core_version",
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
        "haywire.core.publishing.pipeline.steps.framework._installed_core_version",
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
    from haywire.core.publishing.pipeline import InvalidSpecifierError

    with pytest.raises(InvalidSpecifierError):
        SharePipeline(_project(tmp_path)).apply_framework("not a specifier")


def test_apply_rejects_a_bare_version(tmp_path):
    """requires_haywire is a specifier, never a bare version — "0.0.34" alone
    is not a valid SpecifierSet."""
    from haywire.core.publishing.pipeline import InvalidSpecifierError

    with pytest.raises(InvalidSpecifierError):
        SharePipeline(_project(tmp_path)).apply_framework("0.0.34")


def test_reordered_equivalent_specifiers_are_not_drift(tmp_path):
    """packaging reorders on str(): ">=0.0.31,<1.0.0" round-trips as
    "<1.0.0,>=0.0.31". Comparing raw strings would report false drift."""
    from haywire.core.publishing.pipeline.steps.framework import specifiers_equal

    assert specifiers_equal(">=0.0.31,<1.0.0", "<1.0.0,>=0.0.31")
    assert not specifiers_equal(">=0.0.31", ">=0.0.34")


def test_marketstall_entry_is_derived_from_the_pyproject_floor(tmp_path, monkeypatch):
    """The entry is a PROJECTION of the floor, not a second authored copy.

    Nothing is passed in: _build_entry_for_library reads the library's own
    pyproject at write time, so the two cannot disagree and a publish cannot
    stamp a stale or empty requirement.
    """
    from haywire.core.publishing.marketstall import _build_entry_for_library

    root = _project(tmp_path)
    SharePipeline(root).apply_framework(">=0.0.34")

    entry = cast(dict, _build_entry_for_library(root / "barn" / "haybale-alpha"))

    assert entry["require"] == "haywire-core>=0.0.34"
    deps = toml.loads((root / "barn" / "haybale-alpha" / "pyproject.toml").read_text())["project"][
        "dependencies"
    ]
    assert "haywire-core>=0.0.34" in deps


def test_entry_emits_a_bare_token_when_the_floor_is_absent(tmp_path):
    """Declared-with-no-floor is a real answer and must survive to the entry."""
    from haywire.core.publishing.marketstall import _build_entry_for_library

    root = _project(tmp_path)
    lib = root / "barn" / "haybale-alpha"
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.1.0"\ndependencies = ["haywire-core"]\n'
    )

    entry = cast(dict, _build_entry_for_library(lib))

    assert entry["require"] == "haywire-core"


def test_entry_omits_require_when_core_is_undeclared(tmp_path):
    """No haywire-core entry at all means no requirement to publish.

    Distinct from the bare-token case above: absent is "nobody answered",
    which the gate reads as "do not block".
    """
    from haywire.core.publishing.marketstall import _build_entry_for_library

    root = _project(tmp_path)
    lib = root / "barn" / "haybale-alpha"
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.1.0"\ndependencies = ["numpy>=1.0"]\n'
    )

    entry = cast(dict, _build_entry_for_library(lib))

    assert entry.get("require", "") == ""


def test_cli_without_the_flag_keeps_the_declared_floor(tmp_path, monkeypatch):
    """No --requires-haywire changes nothing and locks nobody out.

    Unlike the drift precedent (where BOTH options mutate and one is lossy),
    doing nothing here is safe, so a refusal would be pointless friction.
    """
    from haywire_studio.packaging import share_cli

    applied: list[str] = []
    monkeypatch.setattr(SharePipeline, "apply_framework", lambda self, spec: _apply_recorder(applied, spec))
    _stub_publish_tail(monkeypatch)

    share_cli._run_publish(
        SharePipeline(_project(tmp_path)), bump="patch", message=None, requires_haywire=None
    )

    assert applied == []


def test_cli_with_the_flag_raises_the_floor(tmp_path, monkeypatch):
    """Raising a floor — the consumer-excluding direction — always requires the
    explicit flag."""
    from haywire_studio.packaging import share_cli

    applied: list[str] = []
    monkeypatch.setattr(SharePipeline, "apply_framework", lambda self, spec: _apply_recorder(applied, spec))
    _stub_publish_tail(monkeypatch)

    share_cli._run_publish(
        SharePipeline(_project(tmp_path)), bump="patch", message=None, requires_haywire=">=0.0.34"
    )

    assert applied == [">=0.0.34"]


def _stub_publish_tail(monkeypatch) -> None:
    """Neutralize everything after the framework decision.

    These two tests are about ONE branch — whether the framework floor is
    written — so the git-mutating remainder of the run is stubbed rather than
    performed. tests/test_share_cli.py covers the full sequence.
    """
    from unittest.mock import AsyncMock

    from haywire.core.publishing.pipeline import (
        BumpResult,
        CommitPlan,
        CommitResult,
        DocsResult,
        PushResult,
    )

    monkeypatch.setattr(SharePipeline, "require_preconditions", lambda self: None)
    monkeypatch.setattr(
        SharePipeline,
        "apply_bump",
        lambda self, spec: BumpResult(version="0.1.1", written=[], lock_refreshed=True),
    )
    monkeypatch.setattr(
        SharePipeline, "apply_docs", AsyncMock(return_value=DocsResult(coverage={}, written=[]))
    )
    monkeypatch.setattr(
        SharePipeline,
        "apply_marketstall",
        lambda self: SimpleNamespace(out_path=Path("marketstall.toml"), warning=None),
    )
    monkeypatch.setattr(SharePipeline, "verify_push_allowed", lambda self: None)
    # apply_bump is stubbed above, so pipeline.version was never set and the
    # real plan_commit would (correctly) refuse.
    monkeypatch.setattr(
        SharePipeline,
        "plan_commit",
        lambda self, message=None: CommitPlan(files=[], message=message or "", tag="v0.1.1"),
    )
    monkeypatch.setattr(
        SharePipeline,
        "apply_commit",
        lambda self, plan: CommitResult(sha="abc1234", tag="v0.1.1", files=[]),
    )
    monkeypatch.setattr(
        SharePipeline,
        "apply_push",
        AsyncMock(return_value=PushResult(remote="origin", branch="main", tag="v0.1.1")),
    )
