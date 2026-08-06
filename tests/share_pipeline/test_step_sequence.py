"""The Share flow's screens and the pipeline's step modules must stay in step.

Adding a step means touching the pipeline, the flow's STEPS tuple, its titles,
its render dispatch, and the CLI. Nothing enforces that; this file does.

The flow is deliberately NOT 1:1 with the pipeline, and by a wider margin than
its predecessor: ``review`` collects every dependency decision and the version
on one screen, ``publish`` runs docs → marketstall → commit → tag → push as one
authorized action. Those are the USER's units of decision. The pipeline keeps
its finer-grained modules because they have separate reasons to exist (detect
is pure and shared with ``haywire deps check``; dependencies owns every write
to one file). So the invariant is not "one screen per module" but the thing
really being protected: **every decision the UI can express has a pipeline
applier behind it, and apply_all reads every one of them.**
"""

from __future__ import annotations

import inspect
import pkgutil

from haywire.core.publishing.pipeline import steps as steps_pkg
from haywire.core.publishing.pipeline.pipeline import SharePipeline

# Screens with no pipeline counterpart: the terminal summary.
_UI_ONLY_STEPS = frozenset({"done"})

# The pipeline's step modules. Order is the order they run in.
#
# "rollback" is deliberately absent from _SCREEN_TO_STEP below: it backs no
# screen of its own. It fires from ShareFlow.fail() when a step past preflight
# has written something and no commit exists yet — cross-cutting over the
# writing steps rather than belonging to one.
_EXPECTED_PIPELINE_STEPS = (
    "preconditions",
    "detect",
    "dependencies",
    "framework",
    "version",
    "docs",
    "commit",
    "push",
    "rollback",
)

# Flow screen → the pipeline step module that backs it. Screens that drive
# several modules name the one they are principally about.
_SCREEN_TO_STEP = {
    "preflight": "preconditions",
    "review": "dependencies",
    "publish": "commit",
}


def _pipeline_step_modules() -> set[str]:
    return {m.name for m in pkgutil.iter_modules(steps_pkg.__path__)}


def test_pipeline_has_exactly_the_expected_step_modules() -> None:
    assert _pipeline_step_modules() == set(_EXPECTED_PIPELINE_STEPS)


def test_every_screen_maps_to_a_real_step_module() -> None:
    modules = _pipeline_step_modules()
    dangling = {screen: step for screen, step in _SCREEN_TO_STEP.items() if step not in modules}
    assert dangling == {}, f"screens pointing at step modules that do not exist: {dangling}"


def test_every_dependency_decision_has_an_applier() -> None:
    """The real guarantee: a decision the UI can express must have somewhere to
    write. A ShareDecisions field wired to a missing applier would fail only
    when a user actually made that choice."""
    for method in ("apply_framework", "apply_removals", "apply_additions", "apply_floors"):
        assert callable(getattr(SharePipeline, method, None)), f"SharePipeline.{method} is missing"


def test_apply_all_covers_every_share_decisions_field() -> None:
    """Adding a decision field without teaching apply_all to write it would
    silently drop the author's answer — the collect-then-apply-once shape makes
    that failure invisible, since nothing writes until the single apply."""
    import dataclasses

    from haywire.core.publishing.pipeline import ShareDecisions

    source = inspect.getsource(SharePipeline.apply_all)
    for field in dataclasses.fields(ShareDecisions):
        assert f"decisions.{field.name}" in source, (
            f"ShareDecisions.{field.name} is never read by apply_all(); the "
            "author's answer would be collected and then dropped."
        )


def test_detect_step_writes_nothing() -> None:
    """Detect is pure — it has consumers beyond the wizard (``haywire deps
    check``), and a reporting path that mutates would surprise every one."""
    from haywire.core.publishing.pipeline.steps import detect

    source = inspect.getsource(detect)
    assert "write_text" not in source
    assert "edit_toml" not in source
    for name in ("apply_framework", "apply_removals", "apply_additions", "apply_floors"):
        assert name not in source


def test_share_flow_screens_are_backed_or_ui_only() -> None:
    """Every screen either drives a pipeline step or admits it renders only.

    The flow is deliberately NOT 1:1 with the step modules: `review` collects
    every dependency decision plus the version on one screen, and `publish`
    runs docs → marketstall → commit → push as one authorized action. Both
    exist because the user makes ONE decision there, not because the pipeline
    has one step.
    """
    from haybale_share._flow.copy import STEPS

    unaccounted = set(STEPS) - set(_SCREEN_TO_STEP) - _UI_ONLY_STEPS
    assert unaccounted == set(), (
        f"the flow has screens nothing backs: {unaccounted}. Map each to a "
        "pipeline step in _SCREEN_TO_STEP, or list it in _UI_ONLY_STEPS if it "
        "renders without writing."
    )


def test_preflight_precedes_every_writing_screen() -> None:
    """Preflight's clean-tree check is what makes the mid-pipeline revert safe:
    anything dirty after it is provably this run's own writes."""
    from haybale_share._flow.copy import STEPS

    assert STEPS.index("preflight") < STEPS.index("review") < STEPS.index("publish")
