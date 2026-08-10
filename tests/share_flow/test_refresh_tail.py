"""The reload tail of `advance_from_publish` — placement and failure posture.

`version` is read from `haybale.toml` at decoration time, so the hot-swap's
rescan picks up the bumped version straight off disk — no environment sync
needed first. That removed a whole step (`apply_sync`/`uv sync`) this file
used to pin; what's left to guard is that the reload still runs after the
push, and still runs even though nothing precedes it anymore.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from haybale_share._flow._state import ShareFlow
from haywire.core.publishing.pipeline import (
    CommitResult,
    PushError,
    PushResult,
    ShareDecisions,
    SharePipeline,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def flow(tmp_path: Path) -> ShareFlow:
    return ShareFlow(pipeline=SharePipeline(tmp_path))


def _stub_publish(flow: ShareFlow, calls: list[str], *, push_raises: bool = False):
    """Patch every step `advance_from_publish` drives, recording call order."""

    async def _docs(*_a, **_kw):
        calls.append("docs")
        return object()

    async def _push(*_a, **_kw):
        calls.append("push")
        if push_raises:
            raise PushError(stderr="push rejected", manual_command="git push origin master --tags")
        return PushResult(remote="origin", branch="master", tag="v1.0.0")

    async def _swap(*_a, **_kw):
        calls.append("reload")

    return (
        patch.object(SharePipeline, "apply_docs", _docs),
        patch.object(SharePipeline, "apply_push", _push),
        patch.object(SharePipeline, "apply_marketstall", lambda *_a, **_kw: _NoWarning()),
        patch.object(SharePipeline, "verify_push_allowed", lambda *_a, **_kw: None),
        patch.object(SharePipeline, "plan_commit", lambda *_a, **_kw: object()),
        patch.object(
            SharePipeline,
            "apply_commit",
            lambda *_a, **_kw: CommitResult(sha="abc12345", tag="v1.0.0", files=[]),
        ),
        patch.object(ShareFlow, "_hot_swap_bumped_libraries", _swap),
    )


class _NoWarning:
    warning = None
    out_path = Path("marketstall.toml")


@pytest.mark.anyio
async def test_reload_runs_after_the_push(flow: ShareFlow) -> None:
    calls: list[str] = []
    patches = _stub_publish(flow, calls)
    for p in patches:
        p.start()
    try:
        await flow.advance_from_publish()
    finally:
        for p in patches:
            p.stop()

    assert calls == ["docs", "push", "reload"]
    assert flow.step == "done"


@pytest.mark.anyio
async def test_reload_does_not_run_when_the_push_fails(flow: ShareFlow) -> None:
    """Sits outside the try/except *after* it, so a push failure short-circuits
    to fail() without reloading a registry for a release that never landed."""
    calls: list[str] = []
    patches = _stub_publish(flow, calls, push_raises=True)
    for p in patches:
        p.start()
    try:
        await flow.advance_from_publish()
    finally:
        for p in patches:
            p.stop()

    assert "reload" not in calls
    assert flow.step != "done"


@pytest.mark.anyio
async def test_the_bump_step_no_longer_touches_the_registry(flow: ShareFlow) -> None:
    """Pressing "Apply and bump" used to evict every bumped library immediately,
    stranding the studio without them across the docs subprocess and the commit.
    The reload belongs to the publish tail now."""
    with (
        patch.object(SharePipeline, "apply_all", lambda *_a, **_kw: []),
        patch.object(SharePipeline, "apply_bump", lambda *_a, **_kw: _BumpNoWarning()),
        patch.object(ShareFlow, "_hot_swap_bumped_libraries") as swap,
    ):
        await flow.advance_from_review(ShareDecisions(), version_spec="patch")

    swap.assert_not_called()
    assert flow.step == "publish"


class _BumpNoWarning:
    lock_warning = None
    version = "1.0.0"
