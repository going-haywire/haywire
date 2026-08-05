"""The wizard's screens and the pipeline's step modules must stay in step.

Adding a step means touching the pipeline, the wizard's STEPS tuple, its
titles, its render dispatch, and the CLI. Nothing enforces that; this file
does.

The wizard is deliberately NOT 1:1 with the pipeline. Six dependency screens
run over two modules — ``detect`` (pure) and ``dependencies`` (every write to
``[project] dependencies``) — because the author makes six decisions about one
file, and splitting one file's mutations across six modules would spread one
concern thin. So the invariant is not "one screen per module" but the thing
that was really being protected: **every screen that writes has a pipeline
applier behind it.**
"""

from __future__ import annotations

import inspect
import pkgutil

from haywire_studio.packaging.share.pipeline import steps as steps_pkg
from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline

# Screens the wizard renders that have no pipeline counterpart: pure UI beats
# (a progress pause, a summary) or a screen whose only job is to show what an
# earlier apply already did.
_UI_ONLY_STEPS = frozenset({"checked", "confirm", "done"})

# The pipeline's step modules. Order is the order they run in.
_EXPECTED_PIPELINE_STEPS = (
    "preconditions",
    "detect",
    "dependencies",
    "framework",
    "version",
    "docs",
    "commit",
    "push",
)

# Wizard screen → the pipeline step module that backs it.
_SCREEN_TO_STEP = {
    "preconditions": "preconditions",
    "detect": "detect",
    "framework": "dependencies",
    "unused": "dependencies",
    "undeclared": "dependencies",
    "floors": "dependencies",
    "version": "version",
    "docs": "docs",
    "commit": "commit",
    "push": "push",
}


def _pipeline_step_modules() -> set[str]:
    return {m.name for m in pkgutil.iter_modules(steps_pkg.__path__)}


def test_pipeline_has_exactly_the_expected_step_modules() -> None:
    assert _pipeline_step_modules() == set(_EXPECTED_PIPELINE_STEPS)


def test_every_wizard_screen_is_ui_only_or_backed_by_a_step() -> None:
    from haybale_marketplace.editors._share_wizard import STEPS

    unaccounted = set(STEPS) - set(_SCREEN_TO_STEP) - _UI_ONLY_STEPS
    assert unaccounted == set(), (
        f"the wizard has screens nothing backs: {unaccounted}. Map each to a "
        "pipeline step in _SCREEN_TO_STEP, or list it in _UI_ONLY_STEPS if it "
        "renders without writing."
    )


def test_every_screen_maps_to_a_real_step_module() -> None:
    modules = _pipeline_step_modules()
    dangling = {screen: step for screen, step in _SCREEN_TO_STEP.items() if step not in modules}
    assert dangling == {}, f"screens pointing at step modules that do not exist: {dangling}"


def test_every_dependency_screen_has_an_applier() -> None:
    """The real guarantee: a screen that writes must have somewhere to write.

    All four dependency screens go through ``steps/dependencies.py``, so each
    needs its own apply method on the pipeline — a screen wired to a missing
    applier would fail only when a user reached it.
    """
    for method in ("apply_framework", "apply_removals", "apply_additions", "apply_floors"):
        assert callable(getattr(SharePipeline, method, None)), f"SharePipeline.{method} is missing"


def test_detect_step_writes_nothing() -> None:
    """Detect is pure — it has consumers beyond the wizard (``haywire deps
    check``), and a reporting path that mutates would surprise every one."""
    from haywire_studio.packaging.share.pipeline.steps import detect

    source = inspect.getsource(detect)
    assert "write_text" not in source
    assert "edit_toml" not in source
    for name in ("apply_framework", "apply_removals", "apply_additions", "apply_floors"):
        assert name not in source


def test_framework_screen_precedes_the_other_dependency_screens() -> None:
    """The framework floor is authored BEFORE anything else touches the file.

    Not for commit atomicity — for carrier ownership. When this ran last,
    ``plan_framework()`` read a value another step had already rewritten, so
    "keep the current declaration" silently raised the floor.
    """
    from haybale_marketplace.editors._share_wizard.copy import STEPS

    assert STEPS.index("detect") < STEPS.index("framework")
    for later in ("unused", "undeclared", "floors"):
        assert STEPS.index("framework") < STEPS.index(later)
    assert STEPS.index("floors") < STEPS.index("version")
