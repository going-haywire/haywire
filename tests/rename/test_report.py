"""Preflight rendering: counts by default, occurrences under --verbose."""

from __future__ import annotations

from pathlib import Path

import pytest

from haywire_studio.packaging.rename.model import (
    Blocker,
    FileChange,
    Occurrence,
    RenamePlan,
    Warning_,
)


def _plan(**kwargs: object) -> RenamePlan:
    base: dict[str, object] = dict(
        old_dist="hay-src",
        new_dist="hay-dst",
        old_module="hay_src",
        new_module="hay_dst",
        workspace_root=Path("/ws"),
        old_lib_dir=Path("/ws/barn/hay-src"),
        new_lib_dir=Path("/ws/barn/hay-dst"),
    )
    base.update(kwargs)
    return RenamePlan(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_header_shows_both_names_and_modules():
    from haywire_studio.packaging.rename.report import render_plan

    out = render_plan(_plan())
    assert "hay-src" in out
    assert "hay-dst" in out
    assert "hay_src" in out
    assert "hay_dst" in out


@pytest.mark.unit
def test_blocker_remedy_is_printed():
    from haywire_studio.packaging.rename.report import render_plan

    out = render_plan(_plan(blockers=[Blocker(message="Tree is dirty", remedy="git stash")]))
    assert "Tree is dirty" in out
    assert "git stash" in out


@pytest.mark.unit
def test_summary_hides_individual_files():
    from haywire_studio.packaging.rename.report import render_plan

    plan = _plan(graph_changes=[FileChange(path=Path("/ws/a.haywire"), kind="graph", count=4)])
    out = render_plan(plan, verbose=False)

    assert "a.haywire" not in out


@pytest.mark.unit
def test_verbose_lists_each_file():
    from haywire_studio.packaging.rename.report import render_plan

    plan = _plan(graph_changes=[FileChange(path=Path("/ws/a.haywire"), kind="graph", count=4)])
    assert "a.haywire" in render_plan(plan, verbose=True)


@pytest.mark.unit
def test_unrecognized_occurrences_are_flagged():
    from haywire_studio.packaging.rename.report import render_plan

    plan = _plan(unrecognized=[Occurrence(path=Path("/ws/a.haywire"), line=0, text="name")])
    out = render_plan(plan)

    assert "unrecognized" in out.lower()
    assert "not patched" in out.lower()


@pytest.mark.unit
def test_warning_remedy_is_printed():
    from haywire_studio.packaging.rename.report import render_plan

    plan = _plan(warnings=[Warning_(message="Storage will not follow", remedy="mv a b")])
    out = render_plan(plan)

    assert "Storage will not follow" in out
    assert "mv a b" in out
