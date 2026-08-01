"""The wizard's step sequence and the pipeline's step modules must agree.

Adding a step means touching the pipeline, the wizard's STEPS tuple, its
titles, its render dispatch, and the CLI. Nothing enforces that; this test
does, by failing when one side gains a step the other never learned about.
Deliberately hardcoded rather than derived — a six-step publish flow that
changes shape roughly never does not need a registry, but it does need a
tripwire.
"""

from __future__ import annotations

import pkgutil

from haywire_studio.share.pipeline import steps as steps_pkg

# Steps the wizard renders that have no pipeline counterpart.
_UI_ONLY_STEPS = frozenset({"checked", "done"})

# The pipeline's six steps, in order. Keep in sync with
# docs/architecture/sharing/share-pipeline-arch.md §2.
_EXPECTED_PIPELINE_STEPS = (
    "preconditions",
    "drift",
    "version",
    "docs",
    "commit",
    "push",
)


def _pipeline_step_modules() -> set[str]:
    return {m.name for m in pkgutil.iter_modules(steps_pkg.__path__)}


def test_pipeline_has_exactly_the_expected_step_modules() -> None:
    assert _pipeline_step_modules() == set(_EXPECTED_PIPELINE_STEPS)


def test_wizard_covers_every_pipeline_step() -> None:
    from haybale_marketplace.editors._share_wizard import STEPS

    missing = set(_EXPECTED_PIPELINE_STEPS) - set(STEPS)
    assert missing == set(), f"the wizard renders no panel for: {missing}"


def test_wizard_adds_only_known_ui_only_steps() -> None:
    from haybale_marketplace.editors._share_wizard import STEPS

    extra = set(STEPS) - set(_EXPECTED_PIPELINE_STEPS) - _UI_ONLY_STEPS
    assert extra == set(), (
        f"the wizard has steps the pipeline does not know about: {extra}. "
        "Add a pipeline step, or list it in _UI_ONLY_STEPS if it is pure UI."
    )


def test_wizard_step_order_follows_the_pipeline() -> None:
    """UI-only steps may be interleaved, but the pipeline steps the wizard
    does render must appear in pipeline order."""
    from haybale_marketplace.editors._share_wizard import STEPS

    rendered = [s for s in STEPS if s in _EXPECTED_PIPELINE_STEPS]
    assert rendered == list(_EXPECTED_PIPELINE_STEPS)
