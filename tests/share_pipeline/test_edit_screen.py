"""The edit screen collects; publish writes.

Placed between preflight and review: preflight's verdict is what makes the
edit safe to offer, and review's decisions (drift, framework floor, version)
must see the edited state — a linked_libraries change after review would
invalidate a decision the user just authorized.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from haybale_share._flow._state import ShareFlow
from haywire.core.publishing.pipeline import LibraryEdit, MetadataPlan


def _flow(**pipeline_attrs) -> tuple[ShareFlow, MagicMock]:
    """A flow over a mocked pipeline, plus the mock itself.

    The mock is returned separately rather than reached through
    ``flow.pipeline``: that attribute is typed as a real ``SharePipeline``, so
    configuring ``return_value`` through it does not type-check.
    """
    pipeline = MagicMock()
    for key, value in pipeline_attrs.items():
        setattr(pipeline, key, value)
    return ShareFlow(pipeline=pipeline), pipeline


def test_edit_is_between_preflight_and_review():
    assert ShareFlow.STEPS == ("preflight", "edit", "review", "publish", "done")


def test_every_step_has_a_panel():
    """show_step_flow raises when a STEPS entry has no panel."""
    from haybale_share._flow import panels

    for step in ShareFlow.STEPS:
        assert hasattr(panels, f"panel_{step}"), step


def test_preflight_advances_into_edit():
    flow, pipeline = _flow()
    pipeline.require_preconditions.return_value = MagicMock()
    pipeline.plan_metadata.return_value = MetadataPlan(edits=[])

    asyncio.run(flow.advance_from_preflight())
    assert flow.step == "edit"


def test_edit_loads_the_plan_at_preflight_time():
    """The form must be populated when the screen renders, not on first click."""
    edit = LibraryEdit(lib_dir=Path("/tmp/x"), name="haybale-x", label="X", on_reload="none")
    flow, pipeline = _flow()
    pipeline.require_preconditions.return_value = MagicMock()
    pipeline.plan_metadata.return_value = MetadataPlan(edits=[edit])

    asyncio.run(flow.advance_from_preflight())
    assert flow.metadata_edits == [edit]


def test_advance_from_edit_validates_and_blocks():
    flow, pipeline = _flow()
    flow.step = "edit"
    flow.metadata_edits = [LibraryEdit(lib_dir=Path("/tmp/x"), name="haybale-x", label="", on_reload="none")]
    pipeline.validate_metadata.return_value = ["haybale-x: label cannot be empty"]

    asyncio.run(flow.advance_from_edit())
    assert flow.step == "edit"
    assert flow.metadata_problems


def test_advance_from_edit_passes_to_review_when_clean():
    flow, pipeline = _flow()
    flow.step = "edit"
    flow.metadata_edits = []
    pipeline.validate_metadata.return_value = []
    pipeline.check_drift.return_value = MagicMock()
    pipeline.plan_framework.return_value = MagicMock()
    pipeline.plan_version.return_value = MagicMock()

    asyncio.run(flow.advance_from_edit())
    assert flow.step == "review"
    assert flow.metadata_problems == []


def test_edit_writes_nothing():
    """Abandoning the flow here must leave the tree untouched — that is what
    makes ShareFlow.fail's revert a narrow, provable operation."""
    flow, pipeline = _flow()
    flow.step = "edit"
    flow.metadata_edits = []
    pipeline.validate_metadata.return_value = []
    pipeline.check_drift.return_value = MagicMock()
    pipeline.plan_framework.return_value = MagicMock()
    pipeline.plan_version.return_value = MagicMock()

    asyncio.run(flow.advance_from_edit())
    pipeline.apply_metadata.assert_not_called()


def test_publish_applies_the_edits():
    flow, pipeline = _flow()
    flow.step = "review"
    edit = LibraryEdit(lib_dir=Path("/tmp/x"), name="haybale-x", label="X", on_reload="none")
    flow.metadata_edits = [edit]
    pipeline.apply_bump.return_value = MagicMock(lock_warning=None)

    asyncio.run(flow.advance_from_review(MagicMock(), version_spec="0.2.0"))
    pipeline.apply_metadata.assert_called_once_with([edit])
