"""The load overlay must never outlive the load that opened it.

``start_chunked_sync`` blocks canvas interaction behind a non-dismissable
backdrop. There is deliberately no way for the user to close it, so if the
overlay survived a load that ended early — cancelled when the editor closed, or
crashed — the user would be stranded looking at a locked canvas with no way
out. These tests pin the ``finally`` that prevents that, for each way a load
can end.

Exercised against ``GraphCanvasManager.start_chunked_sync`` itself (with the
canvas construction stubbed) rather than a hand-rolled copy of its task body,
so the guarantee is tested where it actually lives.
"""

import asyncio

import pytest
from unittest.mock import MagicMock, patch

from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager

pytestmark = pytest.mark.unit

_MODAL_PATH = "haybale_graph_editor.editors.graph_canvas.graph_canvas_manager.graph_load_modal"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
async def nicegui_loop():
    """Point NiceGUI's global loop at the running one.

    ``background_tasks.create`` asserts ``core.loop is not None``; outside a
    served app nothing sets it. Restored after, so this never leaks into the
    tests that run next.
    """
    from nicegui import core

    previous = core.loop
    core.loop = asyncio.get_running_loop()
    try:
        yield
    finally:
        core.loop = previous


def _manager(sync_impl) -> GraphCanvasManager:
    """A GraphCanvasManager with __init__ bypassed and only what the method touches."""
    mgr = object.__new__(GraphCanvasManager)
    mgr.graph = MagicMock()
    mgr.graph.node_wrappers = {"n0": MagicMock()}
    mgr.session_id = "test"
    mgr._sync_task = None
    mgr.visual_layer = MagicMock()
    mgr.visual_layer.sync_with_graph_chunked = sync_impl
    return mgr


async def _drain(mgr) -> None:
    """Await the background task, swallowing cancellation."""
    task = mgr._sync_task
    if task is None:
        return
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.anyio
async def test_modal_closes_on_success():
    async def ok(on_progress=None, on_phase=None):
        return None

    with patch(_MODAL_PATH) as factory:
        mgr = _manager(ok)
        mgr.start_chunked_sync()
        await _drain(mgr)

    factory.return_value.close.assert_called_once()


@pytest.mark.anyio
async def test_modal_closes_when_the_load_is_cancelled():
    """The editor closing mid-load must not strand the overlay."""

    async def slow(on_progress=None, on_phase=None):
        await asyncio.sleep(60)

    with patch(_MODAL_PATH) as factory:
        mgr = _manager(slow)
        mgr.start_chunked_sync()
        await asyncio.sleep(0)
        mgr._sync_task.cancel()
        await _drain(mgr)

    factory.return_value.close.assert_called_once()


@pytest.mark.anyio
async def test_modal_closes_when_the_load_raises():
    async def boom(on_progress=None, on_phase=None):
        raise RuntimeError("mount blew up")

    with patch(_MODAL_PATH) as factory:
        mgr = _manager(boom)
        mgr.start_chunked_sync()
        with pytest.raises(RuntimeError):
            await mgr._sync_task

    factory.return_value.close.assert_called_once()


@pytest.mark.anyio
async def test_on_complete_does_not_run_when_cancelled():
    """Centring the viewport on a half-mounted graph would frame the wrong thing."""
    called = []

    async def slow(on_progress=None, on_phase=None):
        await asyncio.sleep(60)

    with patch(_MODAL_PATH):
        mgr = _manager(slow)
        mgr.start_chunked_sync(on_complete=lambda: called.append(1))
        await asyncio.sleep(0)
        mgr._sync_task.cancel()
        await _drain(mgr)

    assert called == []


@pytest.mark.anyio
async def test_progress_is_wired_to_the_modal():
    """The loader's per-node callback must reach the overlay's readout."""
    seen = {}

    async def report(on_progress=None, on_phase=None):
        seen["cb"] = on_progress

    with patch(_MODAL_PATH) as factory:
        mgr = _manager(report)
        mgr.start_chunked_sync()
        await _drain(mgr)

    assert seen["cb"] == factory.return_value.advance
