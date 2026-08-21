"""FarmhandContext: DI accessors, broadcast, offload, fence, progress."""

import asyncio
import threading

import pytest

from haywire.core.farmhand import FarmhandContext

pytestmark = pytest.mark.unit


def test_offload_runs_off_the_calling_thread():
    ctx = FarmhandContext()

    async def scenario():
        return await ctx.offload(lambda: threading.current_thread().name)

    worker_thread = asyncio.run(scenario())
    assert worker_thread != threading.main_thread().name


def test_progress_is_noop_without_reporter():
    ctx = FarmhandContext()
    asyncio.run(ctx.progress("hello"))  # must not raise


def test_progress_calls_injected_reporter():
    seen: list[str] = []

    async def reporter(message: str) -> None:
        seen.append(message)

    ctx = FarmhandContext(progress_reporter=reporter)
    asyncio.run(ctx.progress("step 1"))
    assert seen == ["step 1"]


def test_fence_delegates_to_editor():
    class FakeEditor:
        def __init__(self):
            self.fences = 0

        def add_fence(self):
            self.fences += 1

    editor = FakeEditor()
    FarmhandContext().fence(editor)
    assert editor.fences == 1


def test_broadcast_uses_ambient_signal_dispatcher(monkeypatch):
    from haywire.core.di import context as di_context

    class FakeDispatcher:
        def __init__(self):
            self.signals = []

        def broadcast(self, signal):
            self.signals.append(signal)

    fake = FakeDispatcher()
    monkeypatch.setattr(di_context, "_signal_dispatcher", fake)
    sentinel = object()
    FarmhandContext().broadcast(sentinel)
    assert fake.signals == [sentinel]
