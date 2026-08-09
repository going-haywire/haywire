"""The sync + reload tail of `advance_from_publish` — placement and order.

Both properties here are invisible at runtime when wrong: the publish still
succeeds, the panel still says "reloaded", and only the version the studio
reports is silently stale. That is exactly how the original bug shipped, so it
is pinned here rather than left to review.
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

    def _sync(*_a, **_kw):
        calls.append("sync")
        return (True, None)

    async def _swap(*_a, **_kw):
        calls.append("reload")

    return (
        patch.object(SharePipeline, "apply_docs", _docs),
        patch.object(SharePipeline, "apply_push", _push),
        patch.object(SharePipeline, "apply_sync", _sync),
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
async def test_sync_runs_after_the_push_and_before_the_reload(flow: ShareFlow) -> None:
    """Order is the whole feature. The reload re-runs @library(...) and reads back
    installed metadata, so syncing after it picks up the PRE-bump version — and
    syncing before the push would put it inside the rollback window."""
    calls: list[str] = []
    patches = _stub_publish(flow, calls)
    for p in patches:
        p.start()
    try:
        await flow.advance_from_publish()
    finally:
        for p in patches:
            p.stop()

    assert calls == ["docs", "push", "sync", "reload"]
    assert flow.step == "done"


@pytest.mark.anyio
async def test_a_failed_sync_warns_but_still_completes_the_share(flow: ShareFlow) -> None:
    """The publish is public by the time the sync runs, so its failure is a
    warning carrying a remedy — never a failed share."""
    calls: list[str] = []
    patches = _stub_publish(flow, calls)
    for p in patches:
        p.start()
    patched_sync = patch.object(
        SharePipeline, "apply_sync", lambda *_a, **_kw: (False, "uv sync failed: boom")
    )
    patched_sync.start()
    try:
        await flow.advance_from_publish()
    finally:
        patched_sync.stop()
        for p in patches:
            p.stop()

    assert flow.step == "done"
    assert flow.error is None
    assert any("uv sync failed" in w for w in flow.warnings)


@pytest.mark.anyio
async def test_neither_runs_when_the_push_fails(flow: ShareFlow) -> None:
    """Both sit outside the try/except *after* it, so a push failure short-circuits
    to fail() without syncing an environment for a release that never landed."""
    calls: list[str] = []
    patches = _stub_publish(flow, calls, push_raises=True)
    for p in patches:
        p.start()
    try:
        await flow.advance_from_publish()
    finally:
        for p in patches:
            p.stop()

    assert "sync" not in calls
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
        patch.object(SharePipeline, "apply_sync") as sync,
        patch.object(ShareFlow, "_hot_swap_bumped_libraries") as swap,
    ):
        await flow.advance_from_review(ShareDecisions(), version_spec="patch")

    sync.assert_not_called()
    swap.assert_not_called()
    assert flow.step == "publish"


class _BumpNoWarning:
    lock_warning = None
    version = "1.0.0"
